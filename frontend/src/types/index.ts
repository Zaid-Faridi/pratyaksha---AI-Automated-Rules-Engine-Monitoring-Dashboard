/**
 * TypeScript Data Models for Pratyaksha Frontend.
 * Matches backend schemas and API payloads.
 */

export type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'INFO';

export type AlertStatus = 'open' | 'verified' | 'dismissed' | 'auto_resolved';

export type ComplianceStatus = 'COMPLIANT' | 'NEEDS_ATTENTION' | 'NON_COMPLIANT';

export interface Centre {
  id: str;
  name: str;
  state: str;
  district: str;
  lat: number;
  lng: number;
  scheme: str;
  created_at: str;
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
}

type str = string;
