// MINIMAL test handler — NO googleapis, NO >>>, NO import.meta, NO await import.
// Used to isolate whether Vercel @vercel-node itself crashes (configuration issue)
// or whether the crash requires the full server bundle.
module.exports = function handler(req, res) {
    res.status(200);
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({
        ok: true,
        status: 'success',
        message: 'Vercel serves api/handler.js CJS correctly — 0 >>> crash',
        url: req.url,
        method: req.method
    }));
};
