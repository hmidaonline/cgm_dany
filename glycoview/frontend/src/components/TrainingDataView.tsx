import { useState, useEffect, useCallback } from 'react';
import {
  Database, Download, RefreshCw, Calendar, Filter, ChevronLeft, ChevronRight,
  Layers, HelpCircle
} from 'lucide-react';
import { API_BASE_URL } from '../config';

interface TrainingDataSummary {
  total_records: number;
  features_count: number;
  targets_count: number;
  all_columns_count: number;
  min_date: string;
  max_date: string;
  tir_pct: number;
  tbr_pct: number;
  tar_pct: number;
  mean_sgv: number;
  min_sgv: number;
  max_sgv: number;
  meal_events: number;
  bolus_events: number;
}

interface ColumnMeta {
  name: string;
  label: string;
  category: string;
  desc: string;
}

const ALL_COLUMNS_SPEC = [
  { key: 'carbs', label: 'Glucides (g)', type: 'carbs' },
  { key: 'bolus', label: 'Bolus (U)', type: 'bolus' },
  { key: 'iob', label: 'IOB (U)', type: 'iob' },
  { key: 'cob', label: 'COB (g)', type: 'cob' },
  { key: 'basal', label: 'Basal (U/h)', type: 'num' },
  { key: 'sgv_lag_5', label: 'SGV t-5m', type: 'num' },
  { key: 'sgv_lag_10', label: 'SGV t-10m', type: 'num' },
  { key: 'sgv_lag_15', label: 'SGV t-15m', type: 'num' },
  { key: 'sgv_lag_20', label: 'SGV t-20m', type: 'num' },
  { key: 'sgv_lag_30', label: 'SGV t-30m', type: 'num' },
  { key: 'sgv_lag_45', label: 'SGV t-45m', type: 'num' },
  { key: 'sgv_lag_60', label: 'SGV t-60m', type: 'num' },
  { key: 'sgv_diff_5', label: 'Vitesse Δ5m', type: 'diff' },
  { key: 'sgv_diff_15', label: 'Vitesse Δ15m', type: 'num' },
  { key: 'sgv_diff2_5', label: 'Accél. Δ²5m', type: 'num' },
  { key: 'sgv_roll_mean_30', label: 'Moy 30m', type: 'num' },
  { key: 'sgv_roll_std_30', label: 'Écart-type 30m', type: 'num' },
  { key: 'sgv_roll_mean_60', label: 'Moy 60m', type: 'num' },
  { key: 'iob_lag_5', label: 'IOB t-5m', type: 'num' },
  { key: 'iob_diff_5', label: 'IOB Δ5m', type: 'num' },
  { key: 'iob_lag_15', label: 'IOB t-15m', type: 'num' },
  { key: 'iob_lag_30', label: 'IOB t-30m', type: 'num' },
  { key: 'cob_lag_5', label: 'COB t-5m', type: 'num' },
  { key: 'cob_diff_5', label: 'COB Δ5m', type: 'num' },
  { key: 'cob_lag_15', label: 'COB t-15m', type: 'num' },
  { key: 'cob_lag_30', label: 'COB t-30m', type: 'num' },
  { key: 'bolus_sum_1h', label: 'Bolus Σ1h', type: 'num' },
  { key: 'carbs_sum_2h', label: 'Carbs Σ2h', type: 'num' },
  { key: 'sin_hour', label: 'Sin Heure', type: 'float' },
  { key: 'cos_hour', label: 'Cos Heure', type: 'float' },
  { key: 'day_of_week', label: 'Jour Sem.', type: 'float' },
  { key: 'target_15m', label: 'Cible +15m', type: 'target' },
  { key: 'target_30m', label: 'Cible +30m', type: 'target_primary' },
  { key: 'target_60m', label: 'Cible +60m', type: 'target' },
  { key: 'target_120m', label: 'Cible +120m', type: 'target' },
];

export default function TrainingDataView() {
  const [data, setData] = useState<any[]>([]);
  const [summary, setSummary] = useState<TrainingDataSummary | null>(null);
  const [columns, setColumns] = useState<ColumnMeta[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Pagination State
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(50);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalRecords, setTotalRecords] = useState<number>(0);
  const [searchDate, setSearchDate] = useState<string>('');
  const [category, setCategory] = useState<string>('all');
  const [sortOrder, setSortOrder] = useState<string>('desc');
  const [selectedColumnView, setSelectedColumnView] = useState<'synthesis' | 'lags' | 'pharmaco' | 'targets' | 'all'>('synthesis');
  const [showDictionary, setShowDictionary] = useState<boolean>(false);

  // Fetch training dataset
  const fetchDataset = useCallback(() => {
    setLoading(true);
    setError(null);

    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
      category,
      sort_order: sortOrder
    });
    if (searchDate) params.append('search_date', searchDate);

    fetch(`${API_BASE_URL}/api/v1/ml/dataset?${params.toString()}`)
      .then(res => {
        if (!res.ok) throw new Error("Erreur de chargement des données d'entraînement.");
        return res.json();
      })
      .then(resData => {
        if (resData.status === 'success') {
          setData(resData.records || []);
          setSummary(resData.summary || null);
          setColumns(resData.columns || []);
          setTotalPages(resData.total_pages || 1);
          setTotalRecords(resData.total_records || 0);
        }
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [page, pageSize, category, sortOrder, searchDate]);

  useEffect(() => {
    fetchDataset();
  }, [fetchDataset]);

  // Handle CSV Download
  const handleDownloadCSV = () => {
    window.open(`${API_BASE_URL}/api/v1/ml/dataset/export`, '_blank');
  };

  // Helper for trend icons
  const renderTrendIcon = (diff: number) => {
    if (diff > 3.0) return <span style={{ color: '#fbbf24', display: 'inline-flex', alignItems: 'center' }}>↑↑ <small>+{diff}</small></span>;
    if (diff > 1.0) return <span style={{ color: '#38bdf8', display: 'inline-flex', alignItems: 'center' }}>↗ <small>+{diff}</small></span>;
    if (diff < -3.0) return <span style={{ color: '#f87171', display: 'inline-flex', alignItems: 'center' }}>↓↓ <small>{diff}</small></span>;
    if (diff < -1.0) return <span style={{ color: '#f87171', display: 'inline-flex', alignItems: 'center' }}>↘ <small>{diff}</small></span>;
    return <span style={{ color: '#94a3b8', display: 'inline-flex', alignItems: 'center' }}>→ <small>{diff > 0 ? `+${diff}` : diff}</small></span>;
  };

  // Helper for SGV badge
  const renderSgvBadge = (sgv: number) => {
    let bg = 'rgba(16, 185, 129, 0.15)';
    let text = '#34d399';
    let border = 'rgba(16, 185, 129, 0.3)';

    if (sgv < 70) {
      bg = 'rgba(239, 68, 68, 0.15)';
      text = '#f87171';
      border = 'rgba(239, 68, 68, 0.3)';
    } else if (sgv > 180) {
      bg = 'rgba(245, 158, 11, 0.15)';
      text = '#fbbf24';
      border = 'rgba(245, 158, 11, 0.3)';
    }

    return (
      <span style={{
        background: bg,
        color: text,
        border: `1px solid ${border}`,
        padding: '0.2rem 0.55rem',
        borderRadius: '8px',
        fontWeight: '700',
        fontSize: '0.85rem',
        display: 'inline-block',
        minWidth: '55px',
        textAlign: 'center'
      }}>
        {Math.round(sgv)}
      </span>
    );
  };

  const glassCard: React.CSSProperties = {
    background: 'rgba(30, 41, 59, 0.7)',
    backdropFilter: 'blur(16px)',
    border: '1px solid rgba(148, 163, 184, 0.12)',
    borderRadius: '16px',
    padding: '1.25rem',
    boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.3)'
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', animation: 'fadeIn 0.3s ease' }}>
      {/* ─── Header Section ─── */}
      <div style={{
        ...glassCard,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '1rem',
        borderLeft: '4px solid #38bdf8'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div style={{
              background: 'linear-gradient(135deg, #0284c7, #38bdf8)',
              borderRadius: '10px',
              padding: '0.45rem',
              display: 'flex'
            }}>
              <Database style={{ width: '22px', height: '22px', color: '#fff' }} />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.35rem', fontWeight: '800', color: '#f8fafc' }}>
                Données d'Entraînement ML & Feature Store
              </h2>
              <div style={{ color: '#94a3b8', fontSize: '0.82rem', marginTop: '0.2rem' }}>
                Données extraites de MongoDB (01/10/2026 à aujourd'hui), rééchantillonnées à 5 min, interpolées et enrichies de 27 features & 4 cibles supervisées.
              </div>
            </div>
          </div>
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={() => setShowDictionary(!showDictionary)}
            style={{
              background: showDictionary ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(148, 163, 184, 0.2)',
              color: showDictionary ? '#38bdf8' : '#cbd5e1',
              borderRadius: '10px',
              padding: '0.55rem 0.95rem',
              fontSize: '0.82rem',
              fontWeight: '600',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              transition: 'all 0.2s ease'
            }}
          >
            <HelpCircle style={{ width: '15px', height: '15px' }} />
            Dictionnaire des Variables
          </button>

          <button
            onClick={handleDownloadCSV}
            style={{
              background: 'linear-gradient(135deg, #10b981, #059669)',
              color: '#fff',
              border: 'none',
              borderRadius: '10px',
              padding: '0.55rem 1rem',
              fontSize: '0.82rem',
              fontWeight: '700',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)',
              transition: 'all 0.2s ease'
            }}
          >
            <Download style={{ width: '15px', height: '15px' }} />
            Exporter CSV ({summary?.total_records || totalRecords})
          </button>

          <button
            onClick={fetchDataset}
            disabled={loading}
            style={{
              background: 'rgba(56, 189, 248, 0.1)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              color: '#38bdf8',
              borderRadius: '10px',
              padding: '0.55rem 0.85rem',
              fontSize: '0.82rem',
              fontWeight: '600',
              cursor: loading ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem'
            }}
          >
            <RefreshCw style={{ width: '15px', height: '15px', animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            Actualiser
          </button>
        </div>
      </div>

      {/* ─── Top KPI Cards ─── */}
      {summary && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '1rem'
        }}>
          {/* Total Samples */}
          <div style={{ ...glassCard, padding: '1rem', textAlign: 'center' }}>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Vecteurs ML Entraînables
            </div>
            <div style={{ fontSize: '1.65rem', fontWeight: '800', color: '#38bdf8', marginTop: '0.2rem' }}>
              {summary.total_records.toLocaleString()}
            </div>
            <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '0.2rem' }}>
              Intervalles de 5 min (100% complet)
            </div>
          </div>

          {/* Features count */}
          <div style={{ ...glassCard, padding: '1rem', textAlign: 'center' }}>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Colonnes / Features
            </div>
            <div style={{ fontSize: '1.65rem', fontWeight: '800', color: '#818cf8', marginTop: '0.2rem' }}>
              {summary.all_columns_count}
            </div>
            <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '0.2rem' }}>
              27 entrées + 4 cibles (+15,+30,+60,+120)
            </div>
          </div>

          {/* TIR */}
          <div style={{ ...glassCard, padding: '1rem', textAlign: 'center' }}>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Cible (70-180 mg/dL)
            </div>
            <div style={{ fontSize: '1.65rem', fontWeight: '800', color: '#34d399', marginTop: '0.2rem' }}>
              {summary.tir_pct}%
            </div>
            <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '0.2rem' }}>
              TBR: <span style={{ color: '#f87171' }}>{summary.tbr_pct}%</span> | TAR: <span style={{ color: '#fbbf24' }}>{summary.tar_pct}%</span>
            </div>
          </div>

          {/* Glycémie Moyenne */}
          <div style={{ ...glassCard, padding: '1rem', textAlign: 'center' }}>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Moyenne Glycémique
            </div>
            <div style={{ fontSize: '1.65rem', fontWeight: '800', color: '#f8fafc', marginTop: '0.2rem' }}>
              {summary.mean_sgv} <span style={{ fontSize: '0.75rem', fontWeight: '400', color: '#64748b' }}>mg/dL</span>
            </div>
            <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '0.2rem' }}>
              Min: {summary.min_sgv} | Max: {summary.max_sgv}
            </div>
          </div>

          {/* Événements Traitements */}
          <div style={{ ...glassCard, padding: '1rem', textAlign: 'center' }}>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Événements Traitements
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: '800', color: '#fbbf24', marginTop: '0.35rem' }}>
              {summary.meal_events} <span style={{ fontSize: '0.75rem', fontWeight: '500', color: '#cbd5e1' }}>Repas</span>
            </div>
            <div style={{ fontSize: '0.72rem', fontWeight: '700', color: '#38bdf8', marginTop: '0.2rem' }}>
              {summary.bolus_events} Bolus d'insuline
            </div>
          </div>
        </div>
      )}

      {/* ─── Feature Dictionary Accordion ─── */}
      {showDictionary && (
        <div style={{
          ...glassCard,
          border: '1px solid rgba(56, 189, 248, 0.3)',
          background: 'rgba(15, 23, 42, 0.85)',
          animation: 'fadeIn 0.3s ease'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <Layers style={{ width: '18px', height: '18px', color: '#38bdf8' }} />
            <span style={{ fontSize: '1rem', fontWeight: '700', color: '#f8fafc' }}>
              Dictionnaire & Spécification des Caractéristiques Extraites
            </span>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '0.85rem'
          }}>
            {columns.map((col, idx) => (
              <div key={idx} style={{
                background: 'rgba(30, 41, 59, 0.5)',
                border: '1px solid rgba(148, 163, 184, 0.1)',
                borderRadius: '10px',
                padding: '0.75rem'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <code style={{ color: '#38bdf8', fontWeight: '700', fontSize: '0.8rem' }}>{col.name}</code>
                  <span style={{
                    fontSize: '0.65rem',
                    background: 'rgba(255, 255, 255, 0.06)',
                    color: '#94a3b8',
                    padding: '0.15rem 0.45rem',
                    borderRadius: '6px'
                  }}>
                    {col.category}
                  </span>
                </div>
                <div style={{ fontSize: '0.82rem', fontWeight: '600', color: '#cbd5e1', marginTop: '0.35rem' }}>
                  {col.label}
                </div>
                <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '0.25rem', lineHeight: 1.3 }}>
                  {col.desc}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ─── Controls & Filter Bar ─── */}
      <div style={{
        ...glassCard,
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1rem',
        padding: '1rem 1.25rem'
      }}>
        {/* Categories Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <Filter style={{ width: '14px', height: '14px' }} /> Filtre :
          </span>
          {[
            { id: 'all', label: 'Tous' },
            { id: 'target', label: 'Cible (70-180)' },
            { id: 'hypo', label: 'Hypo (<70)' },
            { id: 'hyper', label: 'Hyper (>180)' },
            { id: 'meals', label: 'Avec Repas' },
            { id: 'bolus', label: 'Avec Bolus' },
          ].map(btn => (
            <button
              key={btn.id}
              onClick={() => {
                setCategory(btn.id);
                setPage(1);
              }}
              style={{
                background: category === btn.id ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                color: category === btn.id ? '#38bdf8' : '#94a3b8',
                border: category === btn.id ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid rgba(148, 163, 184, 0.1)',
                borderRadius: '8px',
                padding: '0.35rem 0.75rem',
                fontSize: '0.75rem',
                fontWeight: category === btn.id ? '700' : '500',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              {btn.label}
            </button>
          ))}
        </div>

        {/* Column Views & Date Filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          {/* Column View Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Colonnes :</span>
            <select
              value={selectedColumnView}
              onChange={(e: any) => setSelectedColumnView(e.target.value)}
              style={{
                background: 'rgba(15, 23, 42, 0.6)',
                border: '1px solid rgba(148, 163, 184, 0.2)',
                borderRadius: '8px',
                color: '#cbd5e1',
                padding: '0.4rem 0.7rem',
                fontSize: '0.78rem',
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              <option value="synthesis">Vue Synthèse Principale</option>
              <option value="lags">Vue CGM & Dynamiques Lags</option>
              <option value="pharmaco">Vue Pharmacocinétique (IOB/COB)</option>
              <option value="targets">Vue Cibles Supervisées (+15,+30,+60,+120)</option>
              <option value="all">Vue Complète (37 colonnes)</option>
            </select>
          </div>

          {/* Date Picker */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Calendar style={{ width: '14px', height: '14px', color: '#94a3b8' }} />
            <input
              type="date"
              value={searchDate}
              onChange={(e) => {
                setSearchDate(e.target.value);
                setPage(1);
              }}
              style={{
                background: 'rgba(15, 23, 42, 0.6)',
                border: '1px solid rgba(148, 163, 184, 0.2)',
                borderRadius: '8px',
                color: '#cbd5e1',
                padding: '0.35rem 0.6rem',
                fontSize: '0.78rem',
                outline: 'none'
              }}
            />
            {searchDate && (
              <button
                onClick={() => {
                  setSearchDate('');
                  setPage(1);
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#f87171',
                  cursor: 'pointer',
                  fontSize: '0.75rem',
                  padding: '2px'
                }}
              >
                ✕
              </button>
            )}
          </div>

          {/* Sort order */}
          <select
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value)}
            style={{
              background: 'rgba(15, 23, 42, 0.6)',
              border: '1px solid rgba(148, 163, 184, 0.2)',
              borderRadius: '8px',
              color: '#cbd5e1',
              padding: '0.4rem 0.6rem',
              fontSize: '0.78rem',
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            <option value="desc">Plus récents d'abord</option>
            <option value="asc">Plus anciens d'abord</option>
          </select>
        </div>
      </div>

      {/* ─── Main Dataset Table ─── */}
      <div style={glassCard}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1rem',
          flexWrap: 'wrap',
          gap: '0.5rem'
        }}>
          <div style={{ fontSize: '0.9rem', fontWeight: '700', color: '#f8fafc' }}>
            Tableau des Données Formatées ({totalRecords.toLocaleString()} entrées trouvées)
          </div>

          {/* Page size select */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.78rem', color: '#94a3b8' }}>
            <span>Afficher par page :</span>
            {[25, 50, 100].map(sz => (
              <button
                key={sz}
                onClick={() => {
                  setPageSize(sz);
                  setPage(1);
                }}
                style={{
                  background: pageSize === sz ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                  color: pageSize === sz ? '#38bdf8' : '#94a3b8',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '0.2rem 0.5rem',
                  cursor: 'pointer',
                  fontWeight: pageSize === sz ? '700' : '400'
                }}
              >
                {sz}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div style={{
            height: '350px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '1rem',
            color: '#94a3b8'
          }}>
            <RefreshCw style={{ width: '32px', height: '32px', animation: 'spin 1s linear infinite', color: '#38bdf8' }} />
            <span>Extraction et formatage des données d'entraînement en cours...</span>
          </div>
        ) : error ? (
          <div style={{
            height: '200px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#f87171'
          }}>
            {error}
          </div>
        ) : data.length === 0 ? (
          <div style={{
            height: '200px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#64748b'
          }}>
            Aucune ligne ne correspond aux filtres sélectionnés.
          </div>
        ) : (
          <div style={{ overflowX: 'auto', borderRadius: '10px' }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '0.78rem',
              textAlign: 'left',
              fontFamily: 'monospace'
            }}>
              <thead>
                <tr style={{
                  background: 'rgba(15, 23, 42, 0.7)',
                  color: '#94a3b8',
                  borderBottom: '1px solid rgba(148, 163, 184, 0.15)'
                }}>
                  <th style={{ padding: '0.75rem 0.6rem', position: 'sticky', left: 0, background: 'rgba(15, 23, 42, 0.95)', zIndex: 2 }}>
                    Date & Heure
                  </th>
                  <th style={{ padding: '0.75rem 0.6rem' }}>Glycémie SGV</th>

                  {/* Columns depending on view */}
                  {selectedColumnView === 'synthesis' && (
                    <>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Δ 5m</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Bolus (U)</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Glucides (g)</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>IOB (U)</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>COB (g)</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Moyenne 30m</th>
                      <th style={{ padding: '0.75rem 0.6rem', color: '#38bdf8' }}>Cible +15m</th>
                      <th style={{ padding: '0.75rem 0.6rem', color: '#38bdf8' }}>Cible +30m</th>
                      <th style={{ padding: '0.75rem 0.6rem', color: '#38bdf8' }}>Cible +60m</th>
                      <th style={{ padding: '0.75rem 0.6rem', color: '#38bdf8' }}>Cible +120m</th>
                    </>
                  )}

                  {selectedColumnView === 'all' && (
                    <>
                      {ALL_COLUMNS_SPEC.map(c => (
                        <th key={c.key} style={{ padding: '0.75rem 0.6rem', color: c.type.startsWith('target') ? '#38bdf8' : '#94a3b8', whiteSpace: 'nowrap' }}>
                          {c.label}
                        </th>
                      ))}
                    </>
                  )}

                  {selectedColumnView === 'lags' && (
                    <>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Lag -5m</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Lag -10m</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Lag -15m</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Lag -30m</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Lag -60m</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Vitesse Δ5m</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Vitesse Δ15m</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Accélération</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Moy 30m</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Écart-type 30m</th>
                    </>
                  )}

                  {selectedColumnView === 'pharmaco' && (
                    <>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Bolus</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Glucides</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>IOB Actif</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>IOB Δ5m</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>IOB -30m</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>COB Actif</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>COB Δ5m</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>COB -30m</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Bolus Cumul 1h</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Glucides Cumul 2h</th>
                    </>
                  )}

                  {selectedColumnView === 'targets' && (
                    <>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Heure (Cycle Sin/Cos)</th>
                      <th style={{ padding: '0.75rem 0.6rem' }}>Jour de semaine</th>
                      <th style={{ padding: '0.75rem 0.6rem', color: '#38bdf8' }}>Cible Future +15m</th>
                      <th style={{ padding: '0.75rem 0.6rem', color: '#38bdf8' }}>Cible Future +30m</th>
                      <th style={{ padding: '0.75rem 0.6rem', color: '#38bdf8' }}>Cible Future +60m</th>
                      <th style={{ padding: '0.75rem 0.6rem', color: '#38bdf8' }}>Cible Future +120m</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {data.map((row, idx) => {
                  const dtStr = row.datetime ? row.datetime.replace('+00:00', '').replace('T', ' ') : '--';
                  return (
                    <tr
                      key={idx}
                      style={{
                        borderBottom: '1px solid rgba(148, 163, 184, 0.06)',
                        background: idx % 2 === 0 ? 'rgba(255, 255, 255, 0.015)' : 'transparent',
                        transition: 'background 0.15s ease'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(56, 189, 248, 0.05)'}
                      onMouseLeave={(e) => e.currentTarget.style.background = idx % 2 === 0 ? 'rgba(255, 255, 255, 0.015)' : 'transparent'}
                    >
                      {/* Fixed Date & Time */}
                      <td style={{
                        padding: '0.65rem 0.6rem',
                        position: 'sticky',
                        left: 0,
                        background: 'rgba(15, 23, 42, 0.95)',
                        zIndex: 1,
                        color: '#cbd5e1'
                      }}>
                        {dtStr}
                      </td>

                      {/* SGV */}
                      <td style={{ padding: '0.65rem 0.6rem' }}>
                        {renderSgvBadge(row.sgv)}
                      </td>

                      {/* View Synthesis */}
                      {selectedColumnView === 'synthesis' && (
                        <>
                          <td style={{ padding: '0.65rem 0.6rem' }}>
                            {renderTrendIcon(row.sgv_diff_5)}
                          </td>
                          <td style={{ padding: '0.65rem 0.6rem' }}>
                            {row.bolus > 0 ? (
                              <span style={{ color: '#38bdf8', fontWeight: '700' }}>{row.bolus} U</span>
                            ) : (
                              <span style={{ color: '#475569' }}>-</span>
                            )}
                          </td>
                          <td style={{ padding: '0.65rem 0.6rem' }}>
                            {row.carbs > 0 ? (
                              <span style={{ color: '#fbbf24', fontWeight: '700' }}>{row.carbs} g</span>
                            ) : (
                              <span style={{ color: '#475569' }}>-</span>
                            )}
                          </td>
                          <td style={{ padding: '0.65rem 0.6rem', color: row.iob > 0.5 ? '#38bdf8' : '#cbd5e1' }}>
                            {row.iob}
                          </td>
                          <td style={{ padding: '0.65rem 0.6rem', color: row.cob > 5 ? '#fbbf24' : '#cbd5e1' }}>
                            {row.cob}
                          </td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#94a3b8' }}>
                            {row.sgv_roll_mean_30}
                          </td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#f8fafc', fontWeight: '600' }}>
                            {row.target_15m != null ? Math.round(row.target_15m) : '--'}
                          </td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#38bdf8', fontWeight: '700' }}>
                            {row.target_30m != null ? Math.round(row.target_30m) : '--'}
                          </td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#f8fafc', fontWeight: '600' }}>
                            {row.target_60m != null ? Math.round(row.target_60m) : '--'}
                          </td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#f8fafc', fontWeight: '600' }}>
                            {row.target_120m != null ? Math.round(row.target_120m) : '--'}
                          </td>
                        </>
                      )}

                      {/* View All: Toutes les 35 autres colonnes */}
                      {selectedColumnView === 'all' && (
                        <>
                          {ALL_COLUMNS_SPEC.map(col => {
                            const val = row[col.key];
                            if (col.type === 'diff') {
                              return <td key={col.key} style={{ padding: '0.65rem 0.6rem', whiteSpace: 'nowrap' }}>{renderTrendIcon(val)}</td>;
                            }
                            if (col.type === 'bolus') {
                              return <td key={col.key} style={{ padding: '0.65rem 0.6rem', whiteSpace: 'nowrap' }}>{val > 0 ? <span style={{ color: '#38bdf8', fontWeight: '700' }}>{val} U</span> : <span style={{ color: '#475569' }}>-</span>}</td>;
                            }
                            if (col.type === 'carbs') {
                              return <td key={col.key} style={{ padding: '0.65rem 0.6rem', whiteSpace: 'nowrap' }}>{val > 0 ? <span style={{ color: '#fbbf24', fontWeight: '700' }}>{val} g</span> : <span style={{ color: '#475569' }}>-</span>}</td>;
                            }
                            if (col.type === 'iob') {
                              return <td key={col.key} style={{ padding: '0.65rem 0.6rem', whiteSpace: 'nowrap', color: val > 0.5 ? '#38bdf8' : '#cbd5e1' }}>{val}</td>;
                            }
                            if (col.type === 'cob') {
                              return <td key={col.key} style={{ padding: '0.65rem 0.6rem', whiteSpace: 'nowrap', color: val > 5 ? '#fbbf24' : '#cbd5e1' }}>{val}</td>;
                            }
                            if (col.type === 'target_primary') {
                              return <td key={col.key} style={{ padding: '0.65rem 0.6rem', whiteSpace: 'nowrap', color: '#38bdf8', fontWeight: '700' }}>{val != null ? Math.round(val) : '--'}</td>;
                            }
                            if (col.type === 'target') {
                              return <td key={col.key} style={{ padding: '0.65rem 0.6rem', whiteSpace: 'nowrap', color: '#f8fafc', fontWeight: '600' }}>{val != null ? Math.round(val) : '--'}</td>;
                            }
                            return (
                              <td key={col.key} style={{ padding: '0.65rem 0.6rem', whiteSpace: 'nowrap', color: '#cbd5e1' }}>
                                {val != null ? (typeof val === 'number' ? Math.round(val * 100) / 100 : val) : '--'}
                              </td>
                            );
                          })}
                        </>
                      )}

                      {/* View Lags */}
                      {selectedColumnView === 'lags' && (
                        <>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#cbd5e1' }}>{row.sgv_lag_5}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#cbd5e1' }}>{row.sgv_lag_10}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#cbd5e1' }}>{row.sgv_lag_15}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#cbd5e1' }}>{row.sgv_lag_30}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#cbd5e1' }}>{row.sgv_lag_60}</td>
                          <td style={{ padding: '0.65rem 0.6rem' }}>{renderTrendIcon(row.sgv_diff_5)}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#cbd5e1' }}>{row.sgv_diff_15}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#cbd5e1' }}>{row.sgv_diff2_5}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#cbd5e1' }}>{row.sgv_roll_mean_30}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#cbd5e1' }}>{row.sgv_roll_std_30}</td>
                        </>
                      )}

                      {/* View Pharmaco */}
                      {selectedColumnView === 'pharmaco' && (
                        <>
                          <td style={{ padding: '0.65rem 0.6rem', color: row.bolus > 0 ? '#38bdf8' : '#475569' }}>{row.bolus} U</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: row.carbs > 0 ? '#fbbf24' : '#475569' }}>{row.carbs} g</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#38bdf8', fontWeight: '600' }}>{row.iob}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#cbd5e1' }}>{row.iob_diff_5}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#cbd5e1' }}>{row.iob_lag_30}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#fbbf24', fontWeight: '600' }}>{row.cob}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#cbd5e1' }}>{row.cob_diff_5}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#cbd5e1' }}>{row.cob_lag_30}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#cbd5e1' }}>{row.bolus_sum_1h}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#cbd5e1' }}>{row.carbs_sum_2h}</td>
                        </>
                      )}

                      {/* View Targets */}
                      {selectedColumnView === 'targets' && (
                        <>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#94a3b8' }}>
                            sin: {row.sin_hour} / cos: {row.cos_hour}
                          </td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#94a3b8' }}>{row.day_of_week}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#f8fafc' }}>{row.target_15m != null ? Math.round(row.target_15m) : '--'}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#38bdf8', fontWeight: '700' }}>{row.target_30m != null ? Math.round(row.target_30m) : '--'}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#f8fafc' }}>{row.target_60m != null ? Math.round(row.target_60m) : '--'}</td>
                          <td style={{ padding: '0.65rem 0.6rem', color: '#f8fafc' }}>{row.target_120m != null ? Math.round(row.target_120m) : '--'}</td>
                        </>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* ─── Pagination Footer ─── */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: '1.25rem',
          paddingTop: '1rem',
          borderTop: '1px solid rgba(148, 163, 184, 0.1)',
          flexWrap: 'wrap',
          gap: '1rem'
        }}>
          <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
            Page <strong style={{ color: '#f8fafc' }}>{page}</strong> sur <strong style={{ color: '#f8fafc' }}>{totalPages}</strong> ({totalRecords.toLocaleString()} lignes au total)
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button
              onClick={() => setPage(1)}
              disabled={page <= 1}
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(148, 163, 184, 0.15)',
                color: page <= 1 ? '#475569' : '#cbd5e1',
                padding: '0.35rem 0.65rem',
                borderRadius: '8px',
                fontSize: '0.78rem',
                cursor: page <= 1 ? 'not-allowed' : 'pointer'
              }}
            >
              Début
            </button>

            <button
              onClick={() => setPage(prev => Math.max(prev - 1, 1))}
              disabled={page <= 1}
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(148, 163, 184, 0.15)',
                color: page <= 1 ? '#475569' : '#cbd5e1',
                padding: '0.35rem 0.65rem',
                borderRadius: '8px',
                fontSize: '0.78rem',
                cursor: page <= 1 ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.2rem'
              }}
            >
              <ChevronLeft style={{ width: '14px', height: '14px' }} /> Précédent
            </button>

            <span style={{ fontSize: '0.8rem', color: '#38bdf8', fontWeight: '700', padding: '0 0.5rem' }}>
              {page}
            </span>

            <button
              onClick={() => setPage(prev => Math.min(prev + 1, totalPages))}
              disabled={page >= totalPages}
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(148, 163, 184, 0.15)',
                color: page >= totalPages ? '#475569' : '#cbd5e1',
                padding: '0.35rem 0.65rem',
                borderRadius: '8px',
                fontSize: '0.78rem',
                cursor: page >= totalPages ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.2rem'
              }}
            >
              Suivant <ChevronRight style={{ width: '14px', height: '14px' }} />
            </button>

            <button
              onClick={() => setPage(totalPages)}
              disabled={page >= totalPages}
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(148, 163, 184, 0.15)',
                color: page >= totalPages ? '#475569' : '#cbd5e1',
                padding: '0.35rem 0.65rem',
                borderRadius: '8px',
                fontSize: '0.78rem',
                cursor: page >= totalPages ? 'not-allowed' : 'pointer'
              }}
            >
              Fin
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
