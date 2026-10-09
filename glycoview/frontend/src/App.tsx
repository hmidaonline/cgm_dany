import { useEffect, useState } from 'react';
import { LayoutDashboard, LineChart, BrainCircuit, Activity, Settings as SettingsIcon } from 'lucide-react';
import GlucoseChart from './components/GlucoseChart';
import PredictionView from './components/PredictionView';
import { API_BASE_URL } from './config';

interface Metrics {
  tir?: number;
  tar?: number;
  tbr?: number;
  gmi?: number;
  mean?: number;
  cv?: number;
  details?: {
    very_low?: number;
    low?: number;
    target?: number;
    high?: number;
    very_high?: number;
  };
  sd?: number;
  daily?: {
    date: string;
    low: number;
    target: number;
    high: number;
  }[];
}

function App() {
  const [metrics, setMetrics] = useState<Metrics>({});
  const [availableDays, setAvailableDays] = useState<{ date: string; low: number; target: number; high: number }[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [activeMenu, setActiveMenu] = useState('dashboard');

  // Load available days from DB
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/v1/analysis/days`)
      .then(res => res.json())
      .then(days => setAvailableDays(days))
      .catch(err => console.error("Error fetching available days:", err));
  }, []);

  // Load metrics (global or for selected day)
  useEffect(() => {
    const url = selectedDate
      ? `${API_BASE_URL}/api/v1/analysis/metrics?date=${selectedDate}`
      : `${API_BASE_URL}/api/v1/analysis/metrics`;

    fetch(url)
      .then(res => res.json())
      .then(data => setMetrics(data))
      .catch(err => console.error("Error fetching metrics:", err));
  }, [selectedDate]);

  const selectedDateFormatted = selectedDate
    ? new Date(selectedDate).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
    : null;

  return (
    <>
      <aside className="sidebar">
        <div className="brand">
          <Activity className="w-6 h-6" style={{ color: "var(--accent)" }} />
          GlycoView
        </div>
        <nav className="nav-menu">
          <div className={`nav-item ${activeMenu === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveMenu('dashboard')}>
            <LayoutDashboard className="w-5 h-5" /> Dashboard
          </div>
          <div className={`nav-item ${activeMenu === 'analysis' ? 'active' : ''}`} onClick={() => setActiveMenu('analysis')}>
            <LineChart className="w-5 h-5" /> Analyses (J3)
          </div>
          <div className={`nav-item ${activeMenu === 'prediction' ? 'active' : ''}`} onClick={() => setActiveMenu('prediction')}>
            <BrainCircuit className="w-5 h-5" /> Prédictions (J4)
          </div>
          <div style={{ flex: 1 }}></div>
          <div className="nav-item">
            <SettingsIcon className="w-5 h-5" /> Paramètres
          </div>
        </nav>
      </aside>

      <div className="main-wrapper">
        <header className="header">
          <div className="header-title" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {activeMenu === 'dashboard' && (
              selectedDate ? (
                <span>Journée du <strong style={{ color: '#60a5fa', textTransform: 'capitalize' }}>{selectedDateFormatted}</strong></span>
              ) : (
                <span>Aperçu Général <small style={{ color: '#10b981', fontSize: '0.8rem', fontWeight: 'normal' }}>● En direct</small></span>
              )
            )}
            {activeMenu === 'analysis' && 'Analyses Statistiques'}
            {activeMenu === 'prediction' && 'Modèles de Prédiction'}
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            {metrics.mean !== undefined ? `Moyenne : ${metrics.mean} mg/dL` : 'Chargement...'}
          </div>
        </header>

        <main className="main-content">
          {activeMenu === 'dashboard' && (
            <>
              {/* Grille des statistiques (s'adapte au jour sélectionné ou global) */}
              <div className="stats-grid">
                <div className="stat-box">
                  <div className="stat-label">TIR (70-180)</div>
                  <div className="stat-value" style={{ color: 'var(--target-in)' }}>
                    {metrics.tir !== undefined ? `${metrics.tir}%` : '--%'}
                  </div>
                </div>
                <div className="stat-box">
                  <div className="stat-label">TAR (&gt;180)</div>
                  <div className="stat-value" style={{ color: 'var(--target-high)' }}>
                    {metrics.tar !== undefined ? `${metrics.tar}%` : '--%'}
                  </div>
                </div>
                <div className="stat-box">
                  <div className="stat-label">TBR (&lt;70)</div>
                  <div className="stat-value" style={{ color: 'var(--target-low)' }}>
                    {metrics.tbr !== undefined ? `${metrics.tbr}%` : '--%'}
                  </div>
                </div>
                <div className="stat-box">
                  <div className="stat-label">GMI Estimé</div>
                  <div className="stat-value" style={{ color: 'var(--accent)' }}>
                    {metrics.gmi !== undefined ? `${metrics.gmi}%` : '--%'}
                  </div>
                </div>
                <div className="stat-box">
                  <div className="stat-label">Variabilité (CV)</div>
                  <div className="stat-value" style={{ color: 'var(--text-primary)' }}>
                    {metrics.cv !== undefined ? `${metrics.cv}%` : '--%'}
                  </div>
                </div>
              </div>

              {/* Composant principal du graphique avec sélecteur de jour */}
              <GlucoseChart
                selectedDate={selectedDate}
                onSelectDate={setSelectedDate}
                availableDays={availableDays}
              />
              
              <div className="card" style={{ marginTop: '1.5rem', borderColor: 'rgba(239, 68, 68, 0.3)', backgroundColor: 'rgba(239, 68, 68, 0.05)' }}>
                <div className="card-title" style={{ color: 'var(--target-low)' }}>⚠️ Avertissement Médical</div>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                  Les prédictions et analyses fournies par cette application sont purement informatives. 
                  Ne jamais les utiliser pour décider d'une dose d'insuline ou modifier un traitement médical.
                </p>
              </div>
            </>
          )}

          {activeMenu === 'analysis' && (
            <div className="card">
              <div className="card-title">Statistiques Détaillées (TIR 70-180)</div>
              
              <div style={{ backgroundColor: 'var(--surface-hover)', borderRadius: '8px', padding: '1rem', marginTop: '1rem' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'center', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-color)' }}>
                      <th style={{ padding: '0.5rem', textAlign: 'left' }}>Date</th>
                      <th style={{ padding: '0.5rem', color: 'var(--target-low)' }}>En-dessous</th>
                      <th style={{ padding: '0.5rem', color: 'var(--target-in)' }}>Dans la cible</th>
                      <th style={{ padding: '0.5rem', color: 'var(--target-high)' }}>Au-dessus</th>
                      <th style={{ padding: '0.5rem' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {availableDays.map((day, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '0.5rem', textAlign: 'left', fontWeight: '500' }}>
                          {new Date(day.date).toLocaleDateString('fr-FR', { weekday: 'short', day: '2-digit', month: '2-digit' })}
                        </td>
                        <td style={{ padding: '0.5rem' }}>{day.low}%</td>
                        <td style={{ padding: '0.5rem', fontWeight: '600' }}>{day.target}%</td>
                        <td style={{ padding: '0.5rem' }}>{day.high}%</td>
                        <td style={{ padding: '0.5rem' }}>
                          <button
                            onClick={() => {
                              setSelectedDate(day.date);
                              setActiveMenu('dashboard');
                            }}
                            style={{
                              background: '#3b82f6',
                              color: 'white',
                              border: 'none',
                              borderRadius: '4px',
                              padding: '0.25rem 0.5rem',
                              fontSize: '0.75rem',
                              cursor: 'pointer'
                            }}
                          >
                            Voir la courbe
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div style={{ marginTop: '2rem' }}>
                <div className="card-title">Détail Global</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '1rem', textAlign: 'center', backgroundColor: 'var(--surface-hover)', padding: '1.5rem', borderRadius: '8px' }}>
                  <div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>Très bas</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{metrics.details?.very_low ?? '--'}%</div>
                  </div>
                  <div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>Bas</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{metrics.details?.low ?? '--'}%</div>
                  </div>
                  <div>
                    <div style={{ color: 'var(--target-in)', fontSize: '0.8rem' }}>Dans la cible</div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--target-in)' }}>{metrics.details?.target ?? '--'}%</div>
                  </div>
                  <div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>Haut</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{metrics.details?.high ?? '--'}%</div>
                  </div>
                  <div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>Très haut</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{metrics.details?.very_high ?? '--'}%</div>
                  </div>
                </div>
                
                <div style={{ display: 'flex', justifyContent: 'center', gap: '3rem', marginTop: '1.5rem', color: 'var(--text-secondary)' }}>
                  <div>SD: <strong>{metrics.sd ?? '--'}</strong></div>
                  <div>HbA1c Estimée: <strong style={{ color: 'var(--text-primary)' }}>{metrics.gmi ?? '--'}%</strong></div>
                </div>
              </div>
            </div>
          )}

          {activeMenu === 'prediction' && (
            <PredictionView />
          )}
        </main>
      </div>
    </>
  );
}

export default App;
