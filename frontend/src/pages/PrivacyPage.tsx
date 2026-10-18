import React from 'react';
import { ShieldCheck, EyeOff, Lock, Clock, Database, CheckCircle2, XCircle, FileText } from 'lucide-react';
import { PratyakshaLogo } from '../components/common/PratyakshaLogo';

export const PrivacyPage: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-12">
      {/* Page Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex justify-center mb-1">
          <PratyakshaLogo size="xl" className="shadow-lg rounded-2xl" />
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
          Privacy-Preserving Video Analytics Charter
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 max-w-2xl mx-auto">
          Pratyaksha is built from the ground up to uphold the Indian Digital Personal Data Protection (DPDP) Act.
          Our edge detection pipeline ensures zero biometric surveillance while providing robust infrastructure and attendance verification.
        </p>
      </div>

      {/* Comparison: What We Collect vs What We NEVER Collect */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Strictly Forbidden / Never Collected */}
        <div className="p-6 rounded-2xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/30 dark:bg-rose-950/20 space-y-4">
          <div className="flex items-center gap-2 text-rose-700 dark:text-rose-400 font-bold text-base">
            <XCircle className="w-5 h-5 flex-shrink-0" />
            <h3>What We NEVER Collect or Store</h3>
          </div>
          <ul className="space-y-3 text-xs text-slate-700 dark:text-slate-300">
            <li className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mt-1.5 flex-shrink-0" />
              <span>
                <strong>No Facial Recognition:</strong> No facial embeddings, biometric markers, or identity matching algorithms are present in the system.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mt-1.5 flex-shrink-0" />
              <span>
                <strong>No Individual Person Tracking:</strong> Trainees and trainers are never individually fingerprinted, tracked across zones, or profiled.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mt-1.5 flex-shrink-0" />
              <span>
                <strong>No Raw Video Archives:</strong> Raw video frames are discarded immediately after in-memory zone counts are calculated on the edge agent.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mt-1.5 flex-shrink-0" />
              <span>
                <strong>No Unblurred Human Crops:</strong> In diagnostic modes, human bounding boxes are heavily blurred with a 35px Gaussian kernel before disk writes.
              </span>
            </li>
          </ul>
        </div>

        {/* What We Collect */}
        <div className="p-6 rounded-2xl border border-teal-200 dark:border-teal-900/60 bg-teal-50/30 dark:bg-teal-950/20 space-y-4">
          <div className="flex items-center gap-2 text-teal-700 dark:text-teal-400 font-bold text-base">
            <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
            <h3>What We Collect & Transmit</h3>
          </div>
          <ul className="space-y-3 text-xs text-slate-700 dark:text-slate-300">
            <li className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-teal-500 mt-1.5 flex-shrink-0" />
              <span>
                <strong>Aggregated Headcounts:</strong> Anonymous integer counts of individuals detected in defined classroom and workshop ROI polygons.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-teal-500 mt-1.5 flex-shrink-0" />
              <span>
                <strong>Equipment Inventories:</strong> Detected counts of stationary sanctioned assets (chairs, workbenches, computers, monitors).
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-teal-500 mt-1.5 flex-shrink-0" />
              <span>
                <strong>Time & Zone Metadata:</strong> ISO-8601 sample timestamps and zone identifiers to cross-reference against approved batch schedules.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-teal-500 mt-1.5 flex-shrink-0" />
              <span>
                <strong>Camera Telemetry:</strong> Periodic heartbeats and feed resolution status to detect offline cameras or camera tampering.
              </span>
            </li>
          </ul>
        </div>
      </div>

      {/* Core Privacy Architecture Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-2">
          <div className="p-2 w-fit rounded-lg bg-gov-50 dark:bg-gov-950 text-gov-600 dark:text-gov-400">
            <EyeOff className="w-5 h-5" />
          </div>
          <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">Zero Biometric Storage</h4>
          <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
            YOLO nano models identify only bounding box coordinates on the edge camera device. No facial points, retina, or body biometric templates are generated.
          </p>
        </div>

        <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-2">
          <div className="p-2 w-fit rounded-lg bg-teal-50 dark:bg-teal-950 text-teal-600 dark:text-teal-400">
            <Lock className="w-5 h-5" />
          </div>
          <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">Edge-Side Anonymization</h4>
          <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
            Saving visual diagnostic frames is OFF by default. If enabled for audit logging, detected persons undergo irreversible Gaussian blurring directly on the edge device.
          </p>
        </div>

        <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-2">
          <div className="p-2 w-fit rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400">
            <Clock className="w-5 h-5" />
          </div>
          <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">90-Day Purge Retention</h4>
          <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
            In accordance with minimal data principles, raw detection events older than 90 days are automatically deleted through database retention jobs.
          </p>
        </div>
      </div>

      {/* DPDP Compliance Notice */}
      <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-100/70 dark:bg-slate-900/60 text-xs text-slate-600 dark:text-slate-400 flex items-start gap-3">
        <FileText className="w-5 h-5 text-gov-600 flex-shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="font-bold text-slate-800 dark:text-slate-200">
            Ministry of Skill Development & Entrepreneurship (MSDE) Alignment
          </p>
          <p className="leading-relaxed">
            Pratyaksha fulfills national monitoring requirements for verifiable attendance auditing and infrastructure tracking under government skilling schemes (PMKVY 4.0, DDU-GKY, STRIVE) without subjecting trainees to continuous biometric surveillance.
          </p>
        </div>
      </div>
    </div>
  );
};
