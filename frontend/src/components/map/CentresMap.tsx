import React, { useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Link } from 'react-router-dom';
import { Centre, ComplianceBreakdown } from '../../types';
import { ScoreRing } from '../common/ScoreRing';
import { StatusBadge } from '../common/StatusBadge';
import { Building2, AlertTriangle, ArrowRight } from 'lucide-react';

interface CentresMapProps {
  centres: Centre[];
  complianceMap?: Record<string, ComplianceBreakdown>;
  selectedCentreId?: string | null;
  onSelectCentre?: (id: string) => void;
  className?: string;
}

// Custom Leaflet DivIcon with dynamic compliance coloring
function createPinIcon(score: number = 100) {
  let color = '#10B981'; // Green
  let border = '#059669';

  if (score < 65) {
    color = '#EF4444'; // Red
    border = '#DC2626';
  } else if (score < 85) {
    color = '#F59E0B'; // Amber
    border = '#D97706';
  }

  const html = `
    <div style="
      background-color: ${color};
      width: 28px;
      height: 28px;
      border-radius: 50%;
      border: 3px solid white;
      box-shadow: 0 4px 10px rgba(0,0,0,0.35);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: bold;
      font-size: 11px;
      font-family: sans-serif;
    ">
      ${Math.round(score)}
    </div>
  `;

  return L.divIcon({
    html,
    className: 'custom-leaflet-marker',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -16],
  });
}

function MapViewController({ centre }: { centre?: Centre }) {
  const map = useMap();
  React.useEffect(() => {
    if (centre) {
      map.flyTo([centre.lat, centre.lng], 9, { duration: 1.2 });
    }
  }, [centre, map]);
  return null;
}

export const CentresMap: React.FC<CentresMapProps> = ({
  centres,
  complianceMap = {},
  selectedCentreId,
  onSelectCentre,
  className = 'h-[550px] w-full',
}) => {
  // Center of India coordinates
  const defaultCenter: [number, number] = [21.5937, 78.9629];
  const defaultZoom = 5;

  const selectedCentre = useMemo(() => {
    return centres.find((c) => c.id === selectedCentreId);
  }, [centres, selectedCentreId]);

  return (
    <div className={`relative rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-sm ${className}`}>
      <MapContainer
        center={defaultCenter}
        zoom={defaultZoom}
        scrollWheelZoom={false}
        className="w-full h-full z-10"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapViewController centre={selectedCentre} />

        {centres.map((c) => {
          const comp = complianceMap[c.id];
          const score = comp ? comp.compliance_score : 90;
          const openAlerts = comp ? comp.open_alerts_count : 0;
          const icon = createPinIcon(score);

          return (
            <Marker
              key={c.id}
              position={[c.lat, c.lng]}
              icon={icon}
              eventHandlers={{
                click: () => onSelectCentre?.(c.id),
              }}
            >
              <Popup className="custom-popup">
                <div className="p-1 min-w-[220px]">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                      {c.scheme}
                    </span>
                    <StatusBadge status={comp?.summary_status || 'COMPLIANT'} />
                  </div>

                  <h4 className="font-bold text-sm text-slate-900 leading-tight mb-1">
                    {c.name}
                  </h4>
                  <p className="text-xs text-slate-500 mb-3">
                    {c.district}, {c.state}
                  </p>

                  <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-100 mb-3">
                    <div className="flex items-center gap-2">
                      <ScoreRing score={score} size="sm" />
                      <div>
                        <span className="text-[10px] text-slate-400 block font-semibold uppercase">Score</span>
                        <span className="text-xs font-bold text-slate-800">{score.toFixed(1)}/100</span>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className="text-[10px] text-slate-400 block font-semibold uppercase">Alerts</span>
                      <span className={`text-xs font-bold ${openAlerts > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                        {openAlerts} Open
                      </span>
                    </div>
                  </div>

                  <Link
                    to={`/centres/${c.id}`}
                    className="w-full inline-flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg bg-gov-600 hover:bg-gov-700 text-white text-xs font-semibold shadow-sm transition"
                  >
                    View Centre Analytics
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
};
