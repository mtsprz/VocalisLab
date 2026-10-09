"""Companion: idempotencia, subida interrumpida, recuperación de jobs,
troceado, enforcement por device, revocación, pairing y contrato de métricas."""
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import companion as C


# ─── Fakes ───
class _R:
    def __init__(self, data):
        self.data = data


class _Q:
    # Ejecución diferida como supabase-py: todo encadena, execute() aplica.
    def __init__(self, db, table):
        self.db = db
        self.table = table
        self._op = None
        self._payload = None
        self._conflict = None
        self._f = []
        self._order = []
        self._limit = None

    def select(self, *a):
        self._op = "select"
        return self

    def insert(self, row):
        self._op = "insert"
        self._payload = row
        return self

    def upsert(self, row, on_conflict=None):
        self._op = "upsert"
        self._payload = row
        self._conflict = on_conflict
        return self

    def update(self, vals):
        self._op = "update"
        self._payload = vals
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, k, v):
        self._f.append(("eq", k, v))
        return self

    def neq(self, k, v):
        self._f.append(("neq", k, v))
        return self

    def in_(self, k, vs):
        self._f.append(("in", k, set(vs)))
        return self

    def lte(self, k, v):
        self._f.append(("lte", k, v))
        return self

    def order(self, k, desc=False):
        self._order.append((k, desc))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def _rows(self):
        import copy
        rows = list(self.db.get(self.table, []))
        for op, k, v in self._f:
            if op == "eq":
                rows = [r for r in rows if r.get(k) == v]
            elif op == "neq":
                rows = [r for r in rows if r.get(k) != v]
            elif op == "in":
                rows = [r for r in rows if r.get(k) in v]
            elif op == "lte":
                rows = [r for r in rows if str(r.get(k) or "") <= str(v)]
        for k, desc in reversed(self._order):
            rows.sort(key=lambda r: str(r.get(k) or ""), reverse=bool(desc))
        if self._limit is not None:
            rows = rows[:self._limit]
        return rows

    def execute(self):
        import copy
        if self._op == "insert":
            r = copy.deepcopy(self._payload)
            r.setdefault("id", f"id-{len(self.db.get(self.table, [])) + 1}")
            self.db.setdefault(self.table, []).append(r)
            return _R([r])
        if self._op == "upsert":
            cols = [c.strip() for c in (self._conflict or "").split(",") if c.strip()]
            rows = self.db.setdefault(self.table, [])
            hit = None
            if cols:
                for r in rows:
                    if all(r.get(c) == self._payload.get(c) for c in cols):
                        hit = r
                        break
            if hit is not None:
                hit.update(copy.deepcopy(self._payload))
                return _R([hit])
            r = copy.deepcopy(self._payload)
            r.setdefault("id", f"id-{len(rows) + 1}")
            rows.append(r)
            return _R([r])
        if self._op == "update":
            out = []
            for r in self._rows():
                r.update(copy.deepcopy(self._payload))
                out.append(r)
            return _R(out)
        if self._op == "delete":
            rows = self._rows()
            self.db[self.table] = [r for r in self.db.get(self.table, []) if r not in rows]
            return _R(rows)
        return _R(self._rows())


class _Storage:
    def __init__(self, files):
        self.files = files

    def from_(self, bucket):
        return self

    def list(self, prefix=""):
        return _R([{"name": p.rsplit("/", 1)[-1]}
                   for p in self.files if p.startswith(prefix)]).data

    def create_signed_upload_url(self, path):
        return {"signedURL": f"https://x/{path}?token=t"}

    def create_signed_url(self, path, secs):
        if path not in self.files:
            raise RuntimeError("no existe")
        return {"signedURL": f"https://x/{path}"}

    def upload(self, path, data, opts=None):
        self.files[path] = bytes(data)
        return {}

    def download(self, path):
        if path not in self.files:
            raise RuntimeError("no existe")
        return self.files[path]

    def remove(self, paths):
        for p in paths:
            self.files.pop(p, None)
        return {}


class _FakeSB:
    def __init__(self):
        self.db = {}
        self.files = {}

    def table(self, name):
        return _Q(self.db, name)

    @property
    def storage(self):
        return _Storage(self.files)


@pytest.fixture()
def sb(monkeypatch):
    fake = _FakeSB()
    monkeypatch.setattr(C, "supabase", fake)
    return fake


@pytest.fixture()
def client(sb):
    app = FastAPI()
    app.include_router(C.router)
    return TestClient(app)


def _dev(sb, prof="prof-1", revoked=False, name="dev"):
    tok = "tok-" + name
    sb.db.setdefault("companion_devices", []).append({
        "id": f"dev-{name}", "profesional_google_id": prof,
        "device_name": name, "token_hash": hashlib.sha256(tok.encode()).hexdigest(),
        "revoked": revoked})
    return tok


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


BASE_SES = {
    "device_session_id": "ds-1", "patient_id": "pac-1",
    "recorded_at": "2026-10-09T10:00:00-03:00", "audio_duration_sec": 120,
    "audio_codec": "opus", "audio_bitrate_kbps": 48, "dsp_version": "dsp/1.0",
    "device_info": {}, "consent_recorded": True,
    "segments": [{"task_type": "vocal_sostenida_a", "speaker": "paciente",
                  "start_sec": 0, "end_sec": 20}],
    "acoustics": [{"task_type": "vocal_sostenida_a", "f0_mean_hz": 210,
                   "f0_median_hz": 209, "f0_sd_semitones": 0.3,
                   "jitter_pct": 0.4, "dsp_version": "dsp/1.0"}],
}


def test_idempotencia_sesiones(client, sb):
    sb.db["pacientes"] = [{"id": "pac-1"}]
    tok = _dev(sb)
    r1 = client.post("/api/companion/sessions", json=dict(BASE_SES), headers=_hdr(tok))
    r2 = client.post("/api/companion/sessions", json=dict(BASE_SES), headers=_hdr(tok))
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["session_id"] == r2.json()["session_id"]
    assert len(sb.db["companion_sessions"]) == 1
    assert len(sb.db["session_acoustics"]) == 1  # sin duplicar métricas


def test_sesion_otro_profesional_403(client, sb):
    sb.db["pacientes"] = [{"id": "pac-1"}]
    sb.db["companion_sessions"] = [{
        "id": "s-9", "patient_id": "pac-1", "profesional_google_id": "prof-2",
        "device_session_id": "ds-9", "status": "uploaded"}]
    tok = _dev(sb, prof="prof-1")
    r = client.get("/api/companion/sessions/s-9", headers=_hdr(tok))
    assert r.status_code == 403


def test_device_revocado_401(client, sb):
    tok = _dev(sb, revoked=True)
    r = client.get("/api/companion/sessions?patient_id=pac-1", headers=_hdr(tok))
    assert r.status_code == 401


def test_confirm_sin_audio_422(client, sb):
    sb.db["pacientes"] = [{"id": "pac-1"}]
    tok = _dev(sb)
    client.post("/api/companion/sessions", json=dict(BASE_SES), headers=_hdr(tok))
    r = client.post("/api/companion/uploads/confirm",
                    json={"device_session_id": "ds-1", "kind": "session_audio"},
                    headers=_hdr(tok))
    assert r.status_code == 422


def test_upload_size_limit_413(client, sb):
    tok = _dev(sb)
    r = client.post("/api/companion/uploads",
                    json={"device_session_id": "ds-1", "kind": "session_audio",
                          "mime": "audio/mp4", "size_bytes": 50 * 1024 * 1024},
                    headers=_hdr(tok))
    assert r.status_code == 413


def test_boot_recovery_reencola(monkeypatch):
    import datetime
    class Q2(_Q):
        pass
    fake = _FakeSB()
    viejo = (datetime.datetime.now(datetime.timezone.utc) -
             datetime.timedelta(minutes=30)).isoformat()
    fake.db["processing_jobs"] = [
        {"id": "j-1", "session_id": "s-1", "status": "processing", "lease_at": viejo}]
    fake.db["companion_sessions"] = [{"id": "s-1", "status": "processing"}]
    monkeypatch.setattr(C, "supabase", fake)
    n = C._boot_recovery()
    assert n == 1
    assert fake.db["processing_jobs"][0]["status"] == "queued"


def test_chunk_plan_simple_y_fallback(monkeypatch):
    assert C._chunk_plan("/tmp/a.m4a", 1024, []) == [("/tmp/a.m4a", 0.0)]
    import shutil
    monkeypatch.setattr(shutil, "which", lambda x: None)
    try:
        C._chunk_plan("/tmp/a.m4a", 30 * 1024 * 1024, [])
        assert False, "debió fallar"
    except RuntimeError:
        pass


def test_validacion_metricas():
    ok, _ = C._validar_acustica_row({
        "f0_mean_hz": 210, "f0_median_hz": 209, "f0_sd_semitones": 0.57,
        "f0_p5_hz": 200, "f0_p95_hz": 220,
        "f0_histogram": {"ref_hz": 209, "bins": {"-1": 50, "0": 200, "1": 50}},
        "f0_contour": [208.0, 209.5, 210.0, 209.0]})
    assert ok is True
    ok2, notas = C._validar_acustica_row({
        "f0_mean_hz": 300, "f0_median_hz": 209, "f0_sd_semitones": 0.25,
        "f0_histogram": {"ref_hz": 209, "bins": {"-1": 50, "0": 200, "1": 50}},
        "f0_contour": []})
    assert ok2 is False and notas


def test_semitones_stats():
    sd, mean, median = C._semitones_stats([200.0, 210.0, 220.0], 210.0)
    assert sd is not None and sd > 0
    assert C._semitones_stats([], 210.0) == (None, None, None)
    assert C._semitones_stats([0, 0], 210.0) == (None, None, None)


def test_pairing_expirado_y_usado(client, sb):
    import datetime
    viejo = (datetime.datetime.now(datetime.timezone.utc) -
             datetime.timedelta(minutes=20)).isoformat()
    sb.db["companion_pairing_codes"] = [
        {"id": "c-1", "code": "VIEJO1", "profesional_google_id": "prof-1",
         "expires_at": viejo, "used": False},
        {"id": "c-2", "code": "USADO1", "profesional_google_id": "prof-1",
         "expires_at": "2999-01-01T00:00:00+00:00", "used": True}]
    assert client.post("/api/companion/pair", json={"code": "VIEJO1"}).status_code == 401
    assert client.post("/api/companion/pair", json={"code": "USADO1"}).status_code == 401
    assert client.post("/api/companion/pair", json={"code": "NOEXISTE"}).status_code == 401


def test_referencia_override_y_rango():
    p = {"sexo": "Femenino", "fecha_nacimiento": "1990-01-01",
         "f0_ref_min_hz": 180, "f0_ref_max_hz": 230}
    r = C._elegir_referencia(p, [])
    assert (r["min_hz"], r["max_hz"], r["origen"]) == (180, 230, "override del paciente")
    p2 = {"sexo": "Femenino", "fecha_nacimiento": "1990-01-01"}
    r2 = C._elegir_referencia(p2, [{"sexo_referencia": "femenino", "f0_min_hz": 190,
                                    "f0_max_hz": 225, "fuente": "t"}])
    assert (r2["min_hz"], r2["max_hz"]) == (190, 225)
