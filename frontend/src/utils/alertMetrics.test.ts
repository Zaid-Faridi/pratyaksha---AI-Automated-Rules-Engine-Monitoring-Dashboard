import { test } from 'node:test';
import assert from 'node:assert/strict';
import { computeAlertMetrics } from './alertMetrics.ts';

test('computeAlertMetrics enforces sum(type counts) = sum(severity counts) = totalAlerts', () => {
  // Test case based on current demo dataset: 6 open alerts
  const sampleOpenAlerts = [
    { id: 7, type: 'CAMERA_OFFLINE', severity: 'HIGH', status: 'open' },
    { id: 6, type: 'INSTRUCTOR_ABSENT', severity: 'HIGH', status: 'open' },
    { id: 5, type: 'NON_FUNCTIONAL_EQUIPMENT', severity: 'MEDIUM', status: 'open' },
    { id: 4, type: 'ATTENDANCE_MISMATCH', severity: 'CRITICAL', status: 'open' },
    { id: 3, type: 'ATTENDANCE_MISMATCH', severity: 'HIGH', status: 'open' },
    { id: 2, type: 'INSTRUCTOR_ABSENT', severity: 'HIGH', status: 'auto_resolved' }, // should be ignored
    { id: 1, type: 'PPE_VIOLATION', severity: 'HIGH', status: 'open' },
  ];

  const metrics = computeAlertMetrics(sampleOpenAlerts);

  // 1. Total open alerts count
  assert.equal(metrics.totalAlerts, 6);

  // 2. Sum of severity counts
  const sumSeverityCounts =
    metrics.severityCounts.CRITICAL +
    metrics.severityCounts.HIGH +
    metrics.severityCounts.MEDIUM +
    metrics.severityCounts.LOW;

  assert.equal(sumSeverityCounts, metrics.totalAlerts);
  assert.equal(metrics.severityCounts.CRITICAL, 1);
  assert.equal(metrics.severityCounts.HIGH, 4);
  assert.equal(metrics.severityCounts.MEDIUM, 1);
  assert.equal(metrics.severityCounts.LOW, 0);

  // 3. Sum of type counts
  const sumTypeCounts = metrics.typeItems.reduce((acc, item) => acc + item.count, 0);
  assert.equal(sumTypeCounts, metrics.totalAlerts);

  // 4. Per-type severity breakdown sum equals item.count
  for (const item of metrics.typeItems) {
    const itemSeveritySum =
      item.severities.CRITICAL +
      item.severities.HIGH +
      item.severities.MEDIUM +
      item.severities.LOW;
    assert.equal(itemSeveritySum, item.count);
  }

  // 5. Verification: sum(type counts) === sum(severity counts) === totalAlerts
  assert.equal(sumTypeCounts, sumSeverityCounts);
  assert.equal(sumTypeCounts, metrics.totalAlerts);
});

test('computeAlertMetrics handles empty array cleanly', () => {
  const metrics = computeAlertMetrics([]);
  assert.equal(metrics.totalAlerts, 0);
  assert.equal(metrics.typeItems.length, 0);
  assert.equal(
    metrics.severityCounts.CRITICAL +
      metrics.severityCounts.HIGH +
      metrics.severityCounts.MEDIUM +
      metrics.severityCounts.LOW,
    0
  );
});

test('computeAlertMetrics sorts by count descending, then severity weight', () => {
  const alerts = [
    { id: 1, type: 'LOW_COUNT_CRIT', severity: 'CRITICAL', status: 'open' },
    { id: 2, type: 'HIGH_COUNT_MED', severity: 'MEDIUM', status: 'open' },
    { id: 3, type: 'HIGH_COUNT_MED', severity: 'MEDIUM', status: 'open' },
    { id: 4, type: 'LOW_COUNT_MED', severity: 'MEDIUM', status: 'open' },
  ];

  const metrics = computeAlertMetrics(alerts);
  assert.equal(metrics.typeItems[0].type, 'HIGH_COUNT_MED'); // count = 2
  assert.equal(metrics.typeItems[1].type, 'LOW_COUNT_CRIT'); // count = 1, critical weight = 4
  assert.equal(metrics.typeItems[2].type, 'LOW_COUNT_MED');  // count = 1, medium weight = 2
});
