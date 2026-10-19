import type { Alert } from '../types/index.ts';

export type AlertSeverityKey = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export const SEVERITY_COLORS: Record<AlertSeverityKey, string> = {
  CRITICAL: '#B91C1C', // Dark Red
  HIGH: '#EA580C',     // Orange
  MEDIUM: '#CA8A04',   // Yellow
  LOW: '#2563EB',      // Blue
};

export const SEVERITY_WEIGHTS: Record<AlertSeverityKey, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
};

export const CANONICAL_TYPE_LABELS: Record<string, string> = {
  ATTENDANCE_MISMATCH: 'Attendance mismatch',
  INFRASTRUCTURE_GAP: 'Infrastructure gap',
  EQUIPMENT_MISSING: 'Infrastructure gap',
  NON_FUNCTIONAL_EQUIPMENT: 'Non-functional equipment',
  EQUIPMENT_INOPERABLE: 'Non-functional equipment',
  PPE_VIOLATION: 'PPE violation',
  SAFETY_EQUIPMENT_MISSING: 'Safety equipment missing',
  CAPACITY_DEFICIT: 'Capacity deficit',
  INSTRUCTOR_ABSENT: 'Instructor absent',
  MANDATORY_SIGNAGE_MISSING: 'Signage missing',
  SIGNAGE_MISSING: 'Signage missing',
  CAMERA_OFFLINE: 'Camera offline',
  CAMERA_TAMPER: 'Camera offline',
  STREAM_TAMPERING: 'Camera offline',
  POOR_CAMERA_QUALITY: 'Camera offline',
  ZONE_IDLE_DURING_BATCH: 'Zone idle during batch',
  GHOST_WORKER: 'Attendance mismatch',
  UNREGISTERED_BATCH: 'Attendance mismatch',
};

export function normalizeSeverity(sev?: string | null): AlertSeverityKey {
  if (!sev) return 'LOW';
  const upper = sev.trim().toUpperCase();
  if (upper === 'CRITICAL') return 'CRITICAL';
  if (upper === 'HIGH') return 'HIGH';
  if (upper === 'MEDIUM' || upper === 'MED') return 'MEDIUM';
  return 'LOW';
}

export interface AlertTypeItem {
  type: string;
  label: string;
  count: number;
  severities: Record<AlertSeverityKey, number>;
  maxSeverityWeight: number;
}

export interface AlertMetrics {
  totalAlerts: number;
  severityCounts: Record<AlertSeverityKey, number>;
  typeItems: AlertTypeItem[];
  maxCount: number;
}

/**
 * Computes single-source-of-truth alert metrics directly from an open-alerts array.
 * Ensures sum(type counts) === sum(severity counts) === totalAlerts.
 */
export function computeAlertMetrics(alerts: (Alert | any)[] = []): AlertMetrics {
  // Filter for open status
  const openAlerts = alerts.filter(
    (a) => (a.status ? String(a.status).toLowerCase() === 'open' : true)
  );

  const severityCounts: Record<AlertSeverityKey, number> = {
    CRITICAL: 0,
    HIGH: 0,
    MEDIUM: 0,
    LOW: 0,
  };

  const typeMap: Record<
    string,
    {
      count: number;
      severities: Record<AlertSeverityKey, number>;
    }
  > = {};

  for (const alert of openAlerts) {
    const sev = normalizeSeverity(alert.severity);
    severityCounts[sev] += 1;

    const rawType = alert.type || 'UNKNOWN';
    if (!typeMap[rawType]) {
      typeMap[rawType] = {
        count: 0,
        severities: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 },
      };
    }
    typeMap[rawType].count += 1;
    typeMap[rawType].severities[sev] += 1;
  }

  const typeItems: AlertTypeItem[] = Object.entries(typeMap).map(([type, data]) => {
    let maxWeight = 0;
    (['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as AlertSeverityKey[]).forEach((s) => {
      if (data.severities[s] > 0 && SEVERITY_WEIGHTS[s] > maxWeight) {
        maxWeight = SEVERITY_WEIGHTS[s];
      }
    });

    return {
      type,
      label: CANONICAL_TYPE_LABELS[type] || type.replace(/_/g, ' '),
      count: data.count,
      severities: data.severities,
      maxSeverityWeight: maxWeight,
    };
  });

  // Sort by count descending, then by highest severity weight descending
  typeItems.sort((a, b) => {
    if (b.count !== a.count) return b.count - a.count;
    return b.maxSeverityWeight - a.maxSeverityWeight;
  });

  const maxCount = Math.max(...typeItems.map((t) => t.count), 1);

  return {
    totalAlerts: openAlerts.length,
    severityCounts,
    typeItems,
    maxCount,
  };
}
