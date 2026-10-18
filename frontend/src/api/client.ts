/**
 * Pratyaksha Typed API Client Module.
 * Integrates with FastAPI backend with seamless offline mock mode support.
 */

import {
  Alert,
  AlertReviewPayload,
  Camera,
  Centre,
  ComplianceBreakdown,
  DashboardSummary,
  CentreAttendanceHistoryItem,
  ZoneInfrastructureStatusItem,
  LiveCameraStatus,
} from '../types';

import {
  mockAlerts,
  mockAttendanceHistory,
  mockCameras,
  mockCentres,
  mockComplianceBreakdowns,
  mockDashboardSummary,
  mockInfrastructureStatus,
} from './mockData';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  if (USE_MOCK) {
    return handleMockRequest<T>(endpoint, options);
  }

  try {
    const response = await fetch(`${BASE_URL}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API ${response.status}: ${errorText || response.statusText}`);
    }

    return await response.json();
  } catch (err) {
    // If local dev server isn't running and request fails, fallback to mock data
    console.warn(`[API] Network request to ${endpoint} failed. Falling back to local mock fixtures.`, err);
    return handleMockRequest<T>(endpoint, options);
  }
}

// In-memory alert store for mock reviews
let localMockAlerts = [...mockAlerts];

function handleMockRequest<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = new URL(endpoint, 'http://localhost');
  const pathname = url.pathname;

  // 1. Dashboard Summary
  if (pathname === '/dashboard/summary') {
    const summary = { ...mockDashboardSummary };
    summary.open_alerts_count = localMockAlerts.filter(a => a.status === 'open').length;
    return Promise.resolve(summary as unknown as T);
  }

  // 2. Centres
  if (pathname === '/centres') {
    const state = url.searchParams.get('state');
    const district = url.searchParams.get('district');
    const scheme = url.searchParams.get('scheme');
    let filtered = [...mockCentres];
    if (state) filtered = filtered.filter(c => c.state === state);
    if (district) filtered = filtered.filter(c => c.district === district);
    if (scheme) filtered = filtered.filter(c => c.scheme === scheme);
    return Promise.resolve(filtered as unknown as T);
  }

  // Centre detail / compliance / attendance / infra
  const centreMatch = pathname.match(/^\/centres\/([^/]+)$/);
  if (centreMatch) {
    const id = centreMatch[1];
    const centre = mockCentres.find(c => c.id === id) || mockCentres[0];
    return Promise.resolve(centre as unknown as T);
  }

  const complianceMatch = pathname.match(/^\/centres\/([^/]+)\/compliance$/);
  if (complianceMatch) {
    const id = complianceMatch[1];
    const comp = mockComplianceBreakdowns[id] || {
      centre_id: id,
      centre_name: 'Skilling Centre',
      compliance_score: 88.0,
      attendance_rate: 0.90,
      infrastructure_availability_rate: 0.90,
      camera_uptime_rate: 1.0,
      open_alerts_count: 0,
      weights: { attendance: 0.45, infrastructure: 0.35, camera: 0.20 },
      summary_status: 'COMPLIANT' as const,
    };
    return Promise.resolve(comp as unknown as T);
  }

  const attHistoryMatch = pathname.match(/^\/centres\/([^/]+)\/attendance-history$/);
  if (attHistoryMatch) {
    const id = attHistoryMatch[1];
    const history = mockAttendanceHistory[id] || mockAttendanceHistory['centre_up_02'];
    return Promise.resolve(history as unknown as T);
  }

  const infraStatusMatch = pathname.match(/^\/centres\/([^/]+)\/infrastructure-status$/);
  if (infraStatusMatch) {
    const id = infraStatusMatch[1];
    const infra = mockInfrastructureStatus[id] || mockInfrastructureStatus['centre_mh_01'];
    return Promise.resolve(infra as unknown as T);
  }

  // 3. Cameras
  if (pathname === '/cameras') {
    const centreId = url.searchParams.get('centre_id');
    let cams = [...mockCameras];
    if (centreId) cams = cams.filter(c => c.centre_id === centreId);
    return Promise.resolve(cams as unknown as T);
  }

  // 4. Alerts
  if (pathname === '/alerts') {
    const centreId = url.searchParams.get('centre_id');
    const type = url.searchParams.get('type');
    const severity = url.searchParams.get('severity');
    const status = url.searchParams.get('status');

    let list = [...localMockAlerts];
    if (centreId) list = list.filter(a => a.centre_id === centreId);
    if (type) list = list.filter(a => a.type === type);
    if (severity) list = list.filter(a => a.severity === severity);
    if (status) list = list.filter(a => a.status === status);

    return Promise.resolve(list as unknown as T);
  }

  // Alert PATCH
  const alertPatchMatch = pathname.match(/^\/alerts\/(\d+)$/);
  if (alertPatchMatch && options?.method === 'PATCH') {
    const id = parseInt(alertPatchMatch[1], 10);
    const body: AlertReviewPayload = options.body ? JSON.parse(options.body as string) : {};
    const alertIdx = localMockAlerts.findIndex(a => a.id === id);
    if (alertIdx >= 0) {
      localMockAlerts[alertIdx] = {
        ...localMockAlerts[alertIdx],
        status: body.status,
        reviewed_by: body.reviewed_by || 'Current User',
        reviewed_at: new Date().toISOString(),
        review_notes: body.review_notes || localMockAlerts[alertIdx].review_notes,
      };
      return Promise.resolve(localMockAlerts[alertIdx] as unknown as T);
    }
  }

  return Promise.resolve({} as unknown as T);
}

// Exported typed API functions

export const api = {
  getDashboardSummary: () => request<DashboardSummary>('/dashboard/summary'),

  getCentres: (filters?: { state?: string; district?: string; scheme?: string }) => {
    const params = new URLSearchParams();
    if (filters?.state) params.set('state', filters.state);
    if (filters?.district) params.set('district', filters.district);
    if (filters?.scheme) params.set('scheme', filters.scheme);
    const query = params.toString() ? `?${params.toString()}` : '';
    return request<Centre[]>(`/centres${query}`);
  },

  getCentre: (id: string) => request<Centre>(`/centres/${id}`),

  getCentreCompliance: (id: string) => request<ComplianceBreakdown>(`/centres/${id}/compliance`),

  getCentreAttendanceHistory: (id: string) =>
    request<CentreAttendanceHistoryItem[]>(`/centres/${id}/attendance-history`),

  getCentreInfrastructureStatus: (id: string) =>
    request<ZoneInfrastructureStatusItem[]>(`/centres/${id}/infrastructure-status`),

  getCameras: (centre_id?: string) => {
    const query = centre_id ? `?centre_id=${centre_id}` : '';
    return request<Camera[]>(`/cameras${query}`);
  },

  getAlerts: (filters?: { centre_id?: string; type?: string; severity?: string; status?: string }) => {
    const params = new URLSearchParams();
    if (filters?.centre_id) params.set('centre_id', filters.centre_id);
    if (filters?.type) params.set('type', filters.type);
    if (filters?.severity) params.set('severity', filters.severity);
    if (filters?.status) params.set('status', filters.status);
    const query = params.toString() ? `?${params.toString()}` : '';
    return request<Alert[]>(`/alerts${query}`);
  },

  getAlert: (id: number) => request<Alert>(`/alerts/${id}`),

  reviewAlert: (id: number, payload: AlertReviewPayload) =>
    request<Alert>(`/alerts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  postCameraHeartbeat: (id: string) =>
    request<{ status: string; camera_id: string; camera_status: string; last_seen_at: string }>(
      `/cameras/${id}/heartbeat`,
      { method: 'POST' }
    ),

  getCameraStreamUrl: (cameraId: string, options?: { claimedAttendance?: number; demo?: boolean }) => {
    const params = new URLSearchParams();
    if (options?.claimedAttendance !== undefined) params.set('claimed_attendance', String(options.claimedAttendance));
    if (options?.demo !== undefined) params.set('demo', String(options.demo));
    const query = params.toString() ? `?${params.toString()}` : '';
    return `${BASE_URL}/cameras/${cameraId}/stream${query}`;
  },

  getCameraSnapshotUrl: (cameraId: string) => {
    return `${BASE_URL}/cameras/${cameraId}/snapshot?t=${Date.now()}`;
  },

  getCameraTelemetryUrl: (cameraId: string) => {
    return `${BASE_URL}/cameras/${cameraId}/telemetry`;
  },

  getCameraLiveStatus: (cameraId: string) =>
    request<LiveCameraStatus>(`/cameras/${cameraId}/live-status`),

  updateDemoConfig: (cameraId: string, payload: { claimed_attendance?: number; demo_mode?: boolean }) =>
    request<{ status: string; camera_id: string; claimed_attendance: number; demo_mode: boolean }>(
      `/cameras/${cameraId}/demo-config`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    ),

  toggleCentreStreaming: (centreId: string, enabled: boolean) =>
    request<{ centre_id: string; centre_name: string; live_streaming_enabled: boolean }>(
      `/centres/${centreId}/streaming`,
      {
        method: 'PUT',
        body: JSON.stringify({ enabled }),
      }
    ),

  // --- Centre Portal & Claimed Attendance Submission ---
  getBatches: (centreId?: string) => {
    const query = centreId ? `?centre_id=${encodeURIComponent(centreId)}` : '';
    return request<any[]>(`/batches${query}`);
  },

  submitAttendance: (payload: { centre_id: string; batch_id: string; date: string; claimed_count: number }) =>
    request<any>('/attendance', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // --- Audit Trail ---
  getAuditLogs: (filters?: { centre_id?: string; alert_id?: number; officer_name?: string; action?: string }) => {
    const params = new URLSearchParams();
    if (filters?.centre_id) params.set('centre_id', filters.centre_id);
    if (filters?.alert_id) params.set('alert_id', String(filters.alert_id));
    if (filters?.officer_name) params.set('officer_name', filters.officer_name);
    if (filters?.action) params.set('action', filters.action);
    const query = params.toString() ? `?${params.toString()}` : '';
    return request<any[]>(`/audit-logs${query}`);
  },

  getAlertAuditTrail: (alertId: number) =>
    request<any[]>(`/alerts/${alertId}/audit-trail`),

  // --- Ministry Reports Export URLs ---
  getReportCsvUrl: (centreId?: string, startDate?: string, endDate?: string) => {
    const params = new URLSearchParams();
    if (centreId) params.set('centre_id', centreId);
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const query = params.toString() ? `?${params.toString()}` : '';
    return `${BASE_URL}/reports/csv${query}`;
  },

  getReportPdfUrl: (centreId?: string, startDate?: string, endDate?: string) => {
    const params = new URLSearchParams();
    if (centreId) params.set('centre_id', centreId);
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const query = params.toString() ? `?${params.toString()}` : '';
    return `${BASE_URL}/reports/pdf${query}`;
  },
};
