import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Upload,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  Download,
  Building,
  Calendar,
  Users,
  Zap,
  Info,
} from 'lucide-react';
import { api } from '../api/client';
import { Centre } from '../types';
import { PratyakshaLogo } from '../components/common/PratyakshaLogo';

interface CsvRow {
  centre_id: string;
  batch_id: string;
  date: string;
  claimed_count: number;
  isValid: boolean;
  error?: string;
}

export const CentrePortalPage: React.FC = () => {
  const queryClient = useQueryClient();

  // Selection state
  const [selectedCentre, setSelectedCentre] = useState<string>('');
  const [selectedBatch, setSelectedBatch] = useState<string>('');
  const [submissionDate, setSubmissionDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [claimedCount, setClaimedCount] = useState<number>(20);

  // Status message
  const [notification, setNotification] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);

  // CSV parsing state
  const [parsedRows, setParsedRows] = useState<CsvRow[]>([]);
  const [isUploadingCsv, setIsUploadingCsv] = useState(false);

  // Fetch Centres
  const { data: centres = [] } = useQuery({
    queryKey: ['centres'],
    queryFn: () => api.getCentres(),
  });

  // Set default centre
  React.useEffect(() => {
    if (centres.length > 0 && !selectedCentre) {
      setSelectedCentre(centres[0].id);
    }
  }, [centres, selectedCentre]);

  // Fetch Batches for Selected Centre
  const { data: batches = [] } = useQuery({
    queryKey: ['batches', selectedCentre],
    queryFn: () => api.getBatches(selectedCentre),
    enabled: Boolean(selectedCentre),
  });

  // Set default batch
  React.useEffect(() => {
    if (batches.length > 0) {
      setSelectedBatch(batches[0].id);
    } else {
      setSelectedBatch('');
    }
  }, [batches]);

  // Single Attendance Submission Mutation
  const submitMutation = useMutation({
    mutationFn: (payload: {
      centre_id: string;
      batch_id: string;
      date: string;
      claimed_count: number;
    }) => api.submitAttendance(payload),
    onSuccess: (data) => {
      setNotification({
        type: 'success',
        message: `Successfully registered claimed attendance (${data.claimed_count} trainees) for batch '${data.batch_id}' on ${data.date}. Rules engine will audit against video sensors.`,
      });
      queryClient.invalidateQueries({ queryKey: ['dashboardSummary'] });
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
    onError: (err: any) => {
      setNotification({
        type: 'error',
        message: `Submission failed: ${err.message || 'Unknown network error'}`,
      });
    },
  });

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCentre || !selectedBatch) {
      setNotification({
        type: 'error',
        message: 'Please select both a training centre and an active batch.',
      });
      return;
    }
    if (claimedCount <= 0) {
      setNotification({
        type: 'error',
        message: 'Claimed trainee count must be greater than zero.',
      });
      return;
    }

    submitMutation.mutate({
      centre_id: selectedCentre,
      batch_id: selectedBatch,
      date: submissionDate,
      claimed_count: Number(claimedCount),
    });
  };

  // CSV Template Download
  const handleDownloadTemplate = () => {
    const csvContent =
      'centre_id,batch_id,date,claimed_count\n' +
      'centre_mh_01,batch_mh_01,2026-10-18,22\n' +
      'centre_up_02,batch_up_01,2026-10-18,20\n' +
      'centre_ka_03,batch_ka_01,2026-10-18,18\n';
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'pratyaksha_attendance_template.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // CSV File Handler
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
      if (lines.length <= 1) {
        setNotification({
          type: 'error',
          message: 'The uploaded CSV file is empty or missing data rows.',
        });
        return;
      }

      const rows: CsvRow[] = [];
      // Skip header line
      for (let i = 1; i < lines.length; i++) {
        const parts = lines[i].split(',').map((p) => p.trim());
        if (parts.length < 4) continue;
        const [cId, bId, dStr, countStr] = parts;
        const count = parseInt(countStr, 10);

        let error: string | undefined;
        if (!cId) error = 'Missing Centre ID';
        else if (!bId) error = 'Missing Batch ID';
        else if (!dStr || !/^\d{4}-\d{2}-\d{2}$/.test(dStr))
          error = 'Invalid date (YYYY-MM-DD required)';
        else if (isNaN(count) || count < 0) error = 'Invalid headcount number';

        rows.push({
          centre_id: cId,
          batch_id: bId,
          date: dStr,
          claimed_count: count || 0,
          isValid: !error,
          error,
        });
      }

      setParsedRows(rows);
      setNotification({
        type: 'success',
        message: `Parsed ${rows.length} rows from CSV. Review before committing upload.`,
      });
    };
    reader.readAsText(file);
  };

  // Submit All Parsed CSV Rows
  const handleBulkUpload = async () => {
    const validRows = parsedRows.filter((r) => r.isValid);
    if (validRows.length === 0) {
      setNotification({
        type: 'error',
        message: 'No valid rows found in the parsed CSV file.',
      });
      return;
    }

    setIsUploadingCsv(true);
    let successCount = 0;
    let failCount = 0;

    for (const row of validRows) {
      try {
        await api.submitAttendance({
          centre_id: row.centre_id,
          batch_id: row.batch_id,
          date: row.date,
          claimed_count: row.claimed_count,
        });
        successCount++;
      } catch (err) {
        failCount++;
      }
    }

    setIsUploadingCsv(false);
    setNotification({
      type: successCount > 0 ? 'success' : 'error',
      message: `Batch submission completed: ${successCount} successful, ${failCount} failed.`,
    });
    setParsedRows([]);
    queryClient.invalidateQueries({ queryKey: ['dashboardSummary'] });
  };

  // Demonstration Seeders
  const handleSeedDemo = (type: 'honest' | 'inflated') => {
    if (!selectedCentre || !selectedBatch) return;
    const count = type === 'honest' ? 18 : 32; // 18 is close to camera detection, 32 triggers mismatch!
    submitMutation.mutate({
      centre_id: selectedCentre,
      batch_id: selectedBatch,
      date: submissionDate,
      claimed_count: count,
    });
  };

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Page Header */}
      <div className="flex items-center gap-3.5">
        <PratyakshaLogo size="lg" className="rounded-xl shadow-sm" />
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            Centre Self-Service Attendance Portal
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Official batch attendance upload for vocational training institutes. Submitted headcounts
            are reconciled automatically with on-premise vision analytics.
          </p>
        </div>
      </div>

      {/* Notification Banner */}
      {notification && (
        <div
          className={`p-4 rounded-xl flex items-start gap-3 border transition-all ${
            notification.type === 'success'
              ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200'
              : 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200'
          }`}
        >
          {notification.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5 text-emerald-600 dark:text-emerald-400" />
          ) : (
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5 text-rose-600 dark:text-rose-400" />
          )}
          <div className="flex-1 text-sm font-medium">{notification.message}</div>
          <button
            onClick={() => setNotification(null)}
            className="text-xs underline hover:opacity-80"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Grid: Direct Form & Demonstration Quick Seeder */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Direct Form Submission */}
        <div className="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
            <Users className="w-5 h-5 text-gov-600 dark:text-gov-400" />
            Direct Batch Submission
          </h2>

          <form onSubmit={handleFormSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-1.5">
                  Training Centre
                </label>
                <select
                  value={selectedCentre}
                  onChange={(e) => setSelectedCentre(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-gov-500"
                >
                  {centres.map((c: Centre) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.district}, {c.state})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-1.5">
                  Training Batch
                </label>
                <select
                  value={selectedBatch}
                  onChange={(e) => setSelectedBatch(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-gov-500"
                >
                  {batches.length === 0 ? (
                    <option value="">No batches registered</option>
                  ) : (
                    batches.map((b: any) => (
                      <option key={b.id} value={b.id}>
                        {b.name} ({b.start_time} - {b.end_time})
                      </option>
                    ))
                  )}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  Date of Session
                </label>
                <input
                  type="date"
                  value={submissionDate}
                  onChange={(e) => setSubmissionDate(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-gov-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                  <Users className="w-3.5 h-3.5 text-slate-400" />
                  Claimed Trainee Attendance
                </label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={claimedCount}
                  onChange={(e) => setClaimedCount(parseInt(e.target.value, 10) || 0)}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-gov-500"
                  required
                />
              </div>
            </div>

            <div className="pt-2 flex items-center justify-between">
              <span className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1">
                <Info className="w-3.5 h-3.5" />
                Sends signed aggregate payload to /attendance endpoint
              </span>

              <button
                type="submit"
                disabled={submitMutation.isPending || !selectedBatch}
                className="px-5 py-2.5 rounded-xl font-medium text-sm text-white bg-gov-600 hover:bg-gov-700 shadow-sm transition-all disabled:opacity-50"
              >
                {submitMutation.isPending ? 'Submitting...' : 'Submit Claimed Record'}
              </button>
            </div>
          </form>
        </div>

        {/* Right Col: Quick Demonstration Seeders */}
        <div className="bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900/60 dark:to-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm flex flex-col justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
              <Zap className="w-5 h-5 text-amber-500" />
              Demo Seeder
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
              Simulate real-world audit scenarios on the selected centre and batch to test rules
              engine triggers.
            </p>

            <div className="space-y-3">
              <button
                type="button"
                onClick={() => handleSeedDemo('honest')}
                disabled={submitMutation.isPending || !selectedBatch}
                className="w-full text-left p-3 rounded-xl border border-emerald-200 dark:border-emerald-800/60 bg-emerald-50/50 dark:bg-emerald-950/20 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 transition-all group"
              >
                <div className="text-xs font-bold text-emerald-800 dark:text-emerald-300 flex items-center justify-between">
                  <span>Honest Attendance (18 Trainees)</span>
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                </div>
                <div className="text-[11px] text-emerald-700 dark:text-emerald-400 mt-1">
                  Claimed matches observed headcounts. Keeps centre in full compliance.
                </div>
              </button>

              <button
                type="button"
                onClick={() => handleSeedDemo('inflated')}
                disabled={submitMutation.isPending || !selectedBatch}
                className="w-full text-left p-3 rounded-xl border border-rose-200 dark:border-rose-800/60 bg-rose-50/50 dark:bg-rose-950/20 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-all group"
              >
                <div className="text-xs font-bold text-rose-800 dark:text-rose-300 flex items-center justify-between">
                  <span>Inflated "Ghost" Batch (32 Trainees)</span>
                  <AlertCircle className="w-4 h-4 text-rose-600" />
                </div>
                <div className="text-[11px] text-rose-700 dark:text-rose-400 mt-1">
                  Exceeds physical count significantly. Automatically triggers ATTENDANCE_MISMATCH
                  alert.
                </div>
              </button>
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-800 text-[11px] text-slate-400 italic">
            Note: Records update immediately. Re-evaluations run in realtime.
          </div>
        </div>
      </div>

      {/* CSV Bulk Upload Section */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-gov-600 dark:text-gov-400" />
              Bulk CSV Attendance Upload
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Upload multiple dates or multiple batch attendance rosters in a single CSV file.
            </p>
          </div>

          <button
            type="button"
            onClick={handleDownloadTemplate}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Download Sample CSV Template
          </button>
        </div>

        {/* Upload Dropzone */}
        <div className="border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-xl p-6 text-center hover:border-gov-400 dark:hover:border-gov-500 transition-all bg-slate-50/50 dark:bg-slate-950/30">
          <Upload className="w-8 h-8 mx-auto text-slate-400 dark:text-slate-500 mb-2" />
          <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
            Select a formatted CSV file to upload
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Columns: centre_id, batch_id, date (YYYY-MM-DD), claimed_count
          </p>
          <input
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            className="mt-3 text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-gov-50 file:text-gov-700 hover:file:bg-gov-100 dark:file:bg-gov-900/40 dark:file:text-gov-300"
          />
        </div>

        {/* Preview of Parsed Rows */}
        {parsedRows.length > 0 && (
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Parsed Rows ({parsedRows.length})
              </span>
              <button
                type="button"
                onClick={handleBulkUpload}
                disabled={isUploadingCsv}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-gov-600 hover:bg-gov-700 shadow-sm transition-all disabled:opacity-50"
              >
                {isUploadingCsv ? 'Uploading...' : 'Commit Upload All Valid Rows'}
              </button>
            </div>

            <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden max-h-60 overflow-y-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-semibold sticky top-0">
                  <tr>
                    <th className="py-2 px-3">Centre ID</th>
                    <th className="py-2 px-3">Batch ID</th>
                    <th className="py-2 px-3">Date</th>
                    <th className="py-2 px-3">Claimed</th>
                    <th className="py-2 px-3">Validation Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {parsedRows.map((row, idx) => (
                    <tr
                      key={idx}
                      className={
                        row.isValid
                          ? 'hover:bg-slate-50 dark:hover:bg-slate-800/40'
                          : 'bg-rose-50/50 dark:bg-rose-950/20 text-rose-700 dark:text-rose-300'
                      }
                    >
                      <td className="py-2 px-3 font-mono">{row.centre_id}</td>
                      <td className="py-2 px-3 font-mono">{row.batch_id}</td>
                      <td className="py-2 px-3">{row.date}</td>
                      <td className="py-2 px-3 font-bold">{row.claimed_count}</td>
                      <td className="py-2 px-3">
                        {row.isValid ? (
                          <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium">
                            <CheckCircle2 className="w-3.5 h-3.5" /> Valid
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-rose-600 dark:text-rose-400 font-medium">
                            <AlertCircle className="w-3.5 h-3.5" /> {row.error}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
