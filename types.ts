export type FollowUpSeverity = 'low' | 'medium' | 'high';

export type FollowUpType = 'REPEATED_FAILURE' | 'MISSING_DELIVERY' | 'FOLLOW_UP_NEEDED' | 'CLINICAL_TREND' | 'PROACTIVE_SUGGESTION';

export type FollowUpDecisionStatus = 'resolved' | 'snoozed' | 'ignored';

export type ClinicalSuggestionEventType = 'shown' | 'applied' | 'snoozed' | 'ignored';

export interface ClinicalSuggestionEvent {
  eventType: ClinicalSuggestionEventType;
  suggestionType: FollowUpType;
  signal: string;
  severity: FollowUpSeverity;
  confidence: number;
  reasonHash: string;
  patientId: string;
  sourceSurface: 'dashboard' | 'patient_card';
  timestamp: string;
  schemaVersion: '1.0';
}

export interface FollowUpAlert {
  type: FollowUpType;
  severity: FollowUpSeverity;
  reason: string;
  suggestedAction: string;
  reasonHash: string;
  cooldownUntil?: string;
  detectedAt?: string;
  signal?: string;
  evidenceSummary?: string;
  confidence?: number;
}

export interface ProactiveSuggestion {
  id: string;
  patientId: string;
  trendId?: string;
  calendarEventId?: string;
  title: string;
  reasoning: string;
  suggestedAction: string;
  recommendedMaterialId?: string;
  priority: 'low' | 'medium' | 'high';
  createdAt: string;
}

export interface ClinicalTrend {
  id: string;
  patientId: string;
  type: 'IMPROVEMENT' | 'STAGNATION' | 'REGRESSION' | 'EMERGING_PATTERN';
  area: string;
  evidence: string;
  confidence: number;
  detectedAt: string;
}


export interface FollowUpHealth {
  lastSuccessfulDelivery?: string;
  alerts: FollowUpAlert[];
  clinicalSignals?: FollowUpAlert[];
}

export interface MaterialAnalyticsEvent {
  id: string;
  material_id: string;
  event_type: 'used_in_guide' | 'suggestion_accepted' | 'suggestion_discarded' | 'material_archived' | 'suggestion_offered';
  guide_id?: string;
  event_context: 'suggestion' | 'enrichment' | 'manual_add' | 'archive' | 'system';
  timestamp: string;
}

export type ClinicalTask = 
  | 'idle' 
  | 'viewing_dashboard' 
  | 'viewing_patient' 
  | 'editing_guide' 
  | 'reviewing_materials' 
  | 'managing_appointments' 
  | 'generating_reports';

export interface ConversationMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

export interface ClinicalContext {
  activePatientId: string | null;
  activeSessionId: string | null;
  activeGuideId: string | null;
  currentView: string;
  recentMaterials: string[];
  currentTask: ClinicalTask;
  activePatientSummary?: {
    name: string;
    age: number;
    diagnosis: string;
    alerts: string[];
    interests: string[];
    chiefComplaint?: string;
    affectedAreas?: string[];
    primaryDiagnosis?: string;
  };
  activeSessionSummary?: {
    date: string;
    summary: string;
  };
  followUpHealth?: FollowUpHealth;
  proactiveClinicalSuggestions?: FollowUpAlert[];
  conversationHistory: ConversationMessage[];
}

export interface ExternalResource {
  id: string;
  title: string;
  description: string;
  url: string;
  source: string;
  category: string;
  tags: string[];
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
}

export type ClinicalArea = 'Voz' | 'Habla' | 'Lenguaje' | 'Deglución' | 'Audiología' | 'Otro';
export type ResourceType = 'guía' | 'juego' | 'ejercicio' | 'otro';
export type PatientProfile = 'pediátrico' | 'adulto' | 'geriátrico' | 'mixto';
export type DeliveryChannel = 'whatsapp' | 'email' | 'impreso';

export interface ClinicalHistoryField {
  id: string;
  label: string;
  type: 'text' | 'textarea' | 'select' | 'checkbox' | 'date';
  options?: string[];
  required: boolean;
}

export interface ClinicalHistorySection {
  section_id: string;
  title: string;
  fields: ClinicalHistoryField[];
}

export interface ClinicalHistoryTemplate {
  id: string;
  clinic_id: string;
  name: string;
  description: string;
  schema_json: ClinicalHistorySection[];
  version: number;
  is_active: boolean;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

export interface ClinicalHistoryRecord {
  id: string;
  clinic_id: string;
  patient_id: string;
  template_id: string;
  template_version: number;
  status: 'draft' | 'reviewed' | 'approved';
  base_data_json: Record<string, any>;
  ai_suggestions_json: Record<string, any>;
  final_data_json: Record<string, any>;
  ai_metadata: {
    prompt?: string;
    response?: string;
    timestamp?: string;
    user_id?: string;
    token_usage?: number;
  }[];
  author_id: string;
  approved_by?: string;
  created_at: string;
  updated_at: string;
}

export interface Material {

  id: string;
  title: string;
  description?: string;
  clinical_area?: ClinicalArea;
  resource_type?: ResourceType;
  media_type?: 'image' | 'video' | 'pdf' | 'audio';
  target_profile?: PatientProfile;
  difficulty_level?: 'easy' | 'medium' | 'hard';
  target_skill?: string;
  phoneme_target?: string;
  delivery_channels?: DeliveryChannel[];
  tags?: string[];
  url?: string;
  quality_score?: number;
  priority?: 'high' | 'medium' | 'low';
  status?: 'active' | 'obsolete' | 'archived';
  verified?: boolean;
  approved_by?: string;
  approved_at?: string;
  created_at?: string;
  source_type?: 'propio' | 'recurso';
  category?: string;
  type?: string;
  format?: string;
}

export interface DocumentItem {
  id: string;
  name: string;
  type: string;
  date: string;
  content: string;
  mimeType: string;
  aiSummary?: string;
}

export interface Report {
  id: string;
  date: string;
  title: string;
  content: string;
  type: "evaluacion" | "seguimiento" | "alta" | "derivacion" | "generico";
}

export interface TreatmentPlan {
  general: string;
  specific: string[];
  strategies: string;
  shortTerm?: string[];
  midTerm?: string[];
  longTerm?: string[];
  frequency?: string;
  homework?: string;
  familyAdherence?: string;
}

export interface HomeGuide {
  id: string;
  patientId: string;
  title: string;
  content: string;
  materialIds: string[];
  status: 'draft' | 'final' | 'sent';
  version: number;
  created_at: string;
  updated_at: string;
  sent_at?: string;
  delivery_method?: 'whatsapp' | 'email' | 'printed' | 'in_person';
  share_token?: string;
}

export interface Patient {
  id: string;
  name: string;
  age: number;
  diagnosis: string;
  location?: string;
  roomId?: string;
  document: string;
  phone: string;
  email: string;
  notes: string;
  interests?: string[];
  alerts?: string[];
  consentSigned?: boolean;
  responsable?: string;
  derivante?: string;
  history: Session[];
  evaluations: Evaluation[];
  documents: DocumentItem[];
  reports: Report[];
  treatmentPlan: TreatmentPlan;
  homeGuide?: HomeGuide;
  anamnesis?: any;
  consultorio?: string;
  // Ficha clinica identity fields
  date_of_birth?: string;
  gender?: string;
  address?: string;
  obra_social?: string;
  emergency_contact?: string;
  emergency_phone?: string;
  quick_status?: 'active_quick' | 'formalized' | 'discarded' | null;
}

export type SessionStatus = 'draft' | 'completed';

export interface Session {
  id: string;
  patientId: string;
  date: string;
  status: SessionStatus;
  type?: string;
  objectives: string;
  observations: string;
  summary: string;
  planUpdates: string;
  associatedMaterialIds: string[];
  nextAction: string;
  nextSteps?: string;
  homework?: string;
  materials?: string;
}

export interface Evaluation {
  id: string;
  date: string;
  testName: string;
  score: number;
  maxScore: number;
  details?: any;
}

export interface ClinicalNote {
  id: string;
  patient_name: string;
  created_at: string;
  transcription: string;
  summary: string;
  category: string;
  tags: string[];
  audio_url: string;
  duration: number;
}

export interface ClinicalPlanningAnalysis {
  motivo_de_consulta_resumido: string;
  datos_clinicos_relevantes: string;
  hipotesis_o_focos_de_trabajo: string;
  evaluaciones_o_baterias_sugeridas: string[];
  que_observar_en_sesion: string;
  objetivos_inmediatos: string[];
  materiales_necesarios: string[];
  estructura_de_sesion_30_min: string;
  riesgos_o_alertas: string[];
  preguntas_para_profundizar: string[];
  borrador_de_plan: string;
}

export interface DistributionLog {
  id: string;
  distribution_id: string;
  patient_id: string;
  status: 'queued' | 'sent' | 'failed';
  medium: 'whatsapp' | 'email';
  recipient_contact: string;
  material_title: string;
  material_url?: string;
  error_message?: string;
  provider_response?: any;
  created_at: string;
  updated_at: string;
}

export interface Reminder {
  id: string;
  patient_id: string;
  material_title: string;
  recipient_contact: string;
  medium: 'whatsapp' | 'email';
  scheduled_at: string;
  status: 'pending' | 'sent' | 'failed' | 'cancelled';
  created_at: string;
  updated_at: string;
}

