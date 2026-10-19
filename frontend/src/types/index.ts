/**
 * TypeScript Data Models for Pratyaksha Frontend.
 * Matches backend schemas and API payloads.
 */

export type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'INFO';

export type AlertStatus = 'open' | 'verified' | 'dismissed' | 'auto_resolved';

export type ComplianceStatus = 'COMPLIANT' | 'NEEDS_ATTENTION' | 'NON_COMPLIANT';

export interface Centre {
  id: string;
  name: string;
  state: string;
  district: string;
  lat: number;
  lng: number;
  scheme: string;
  trade_id?: string;
  trade_overrides?: Record<string, any>;
  compliance_score?: number;
  live_streaming_enabled?: boolean;
  created_at: string;
}

export interface LiveZoneTelemetry {
  raw_count: number;
  smoothed_count: number;
  claimed_attendance: number;
  attendance_ratio: number;
  attendance_status: 'MATCH' | 'MISMATCH';
}

export interface LiveEquipmentStatus {
  zone: string;
  item: string;
  expected: number;
  detected: number;
  status: 'MATCH' | 'DEFICIT' | 'SURPLUS';
  operability?: 'operational' | 'uncertain' | 'non_operational' | 'missing';
  signals?: Record<string, any>;
}

export interface LiveAlertTickerItem {
  id: string;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical' | 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  message: string;
  timestamp: string;
}

export interface LiveComplianceMetrics {
  instructor_present: boolean;
  ppe_compliance: {
    wearing_count: number;
    total_persons: number;
    compliance_rate: number;
    status: 'COMPLIANT' | 'DEFICIT';
  };
  safety_items: {
    fire_extinguisher: boolean;
    first_aid_box: boolean;
    status: 'COMPLIANT' | 'DEFICIT';
  };
  mandatory_signage: {
    biometric_device: boolean;
    signage: boolean;
    status: 'COMPLIANT' | 'DEFICIT';
  };
  workstation_capacity: {
    claimed: number;
    capacity: number;
    status: 'COMPLIANT' | 'DEFICIT';
  };
  activity_state: 'ACTIVE' | 'IDLE' | 'EMPTY';
}

export interface LiveTelemetryPayload {
  camera_id: string;
  centre_id: string;
  trade_id?: string;
  trade_name?: string;
  centre_name?: string;
  scenario?: string;
  timestamp: string;
  fps: number;
  status: 'online' | 'offline' | 'tampered';
  zones: Record<string, LiveZoneTelemetry>;
  total_persons_detected: number;
  claimed_attendance: number;
  active_batch?: {
    name: string;
    zone: string;
    claimed_attendance: number;
  };
  equipment: LiveEquipmentStatus[];
  compliance_metrics?: LiveComplianceMetrics;
  recent_alerts: LiveAlertTickerItem[];
}

export interface WallCentreItem {
  centre_id: string;
  centre_name: string;
  state: string;
  district: string;
  trade_id: string;
  camera_id: string;
  stream_url: string;
  snapshot_url: string;
  current_headcount: number;
  claimed_attendance: number;
  compliance_score: number;
  active_alerts_count: number;
  camera_status: string;
  current_scenario: string;
}

export interface TradeProfile {
  id: string;
  name: string;
  category: string;
  description: string;
  sanctioned_equipment: any[];
  required_ppe: any[];
  safety_items: any[];
  mandatory_signage: any[];
  workstation_capacity_rule: Record<string, any>;
  compliance_checks: Record<string, boolean>;
  created_at?: string;
  updated_at?: string;
}

export interface LiveCameraStatus {
  camera_id: string;
  centre_id: string;
  camera_status: string;
  live_streaming_allowed: boolean;
  is_streaming: boolean;
  viewer_count: number;
  current_fps: number;
  claimed_attendance: number;
  latest_telemetry?: LiveTelemetryPayload | null;
}

export interface Camera {
  id: str;
  centre_id: str;
  zone_names: str[];
  status: 'online' | 'offline' | 'tampered';
  last_seen_at?: str | null;
  rtsp_url?: str | null;
  created_at: str;
}

export interface SanctionedInventory {
  id: number;
  centre_id: str;
  zone: str;
  item: str;
  expected_count: number;
  created_at: str;
}

export interface Batch {
  id: str;
  centre_id: str;
  name: str;
  start_time: str;
  end_time: str;
  days: str[];
  zone?: str | null;
  created_at: str;
}

export interface AttendanceRecord {
  id: number;
  centre_id: str;
  batch_id: str;
  date: str;
  claimed_count: number;
  submitted_at: str;
}

export interface Alert {
  id: number;
  centre_id: str;
  camera_id?: str | null;
  zone?: str | null;
  item?: str | null;
  type: str;
  severity: Severity;
  message: str;
  evidence_thumbnail_path?: str | null;
  created_at: str;
  status: AlertStatus;
  reviewed_by?: str | null;
  reviewed_at?: str | null;
  review_notes?: str | null;
}

export interface AlertReviewPayload {
  status: 'verified' | 'dismissed' | 'open';
  reviewed_by?: str;
  officer_name?: str;
  review_notes?: str;
}

export interface ComplianceWeights {
  attendance: number;
  infrastructure: number;
  camera: number;
}

export interface ComplianceBreakdown {
  centre_id: str;
  centre_name: str;
  compliance_score: number;
  attendance_rate: number;
  infrastructure_availability_rate: number;
  camera_uptime_rate: number;
  open_alerts_count: number;
  weights: ComplianceWeights;
  summary_status: ComplianceStatus;
}

export interface ComplianceTrendPoint {
  date: str;
  full_date: str;
  average_score: number;
  centres_evaluated: number;
}

export interface DashboardSummary {
  total_centres: number;
  total_cameras: number;
  online_cameras: number;
  offline_cameras: number;
  total_batches: number;
  total_claimed_attendance: number;
  total_observed_attendance: number;
  open_alerts_count: number;
  alerts_by_type: Record<str, number>;
  alerts_by_severity: Record<str, number>;
  top_non_compliant_centres: ComplianceBreakdown[];
  average_compliance_score: number;
  attendance_mismatches_today: number;
  compliance_trend: ComplianceTrendPoint[];
}

export interface CentreAttendanceHistoryItem {
  date: str;
  batch_id: str;
  batch_name: str;
  claimed_count: number;
  detected_count: number;
  mismatch: boolean;
  ratio: number;
}

export interface ZoneInfrastructureStatusItem {
  zone: str;
  item: str;
  expected: number;
  detected: number;
  status: 'MATCH' | 'DEFICIT' | 'SURPLUS';
  operability?: 'operational' | 'uncertain' | 'non_operational' | 'missing';
  signals?: Record<string, any>;
}

export interface AuditLog {
  id: number;
  centre_id: str;
  alert_id?: number | null;
  officer_name: str;
  action: str;
  notes?: str | null;
  timestamp: str;
}

export interface AttendanceSubmission {
  centre_id: str;
  batch_id: str;
  date: str;
  claimed_count: number;
}

type str = string;
