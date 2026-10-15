import { useEffect, useState } from 'react';
import {
  LayoutDashboard, LineChart, BrainCircuit, Activity,
  Cpu, Database, LogOut, ShieldCheck, PanelLeftClose, PanelLeftOpen, Zap
} from 'lucide-react';
import GlucoseChart from './components/GlucoseChart';
import PredictionView from './components/PredictionView';
import DigitalTwinView from './components/DigitalTwinView';
import TrainingDataView from './components/TrainingDataView';
import RLAgentView from './components/RLAgentView';
import LoginView from './components/LoginView';
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
  const [currentUser, setCurrentUser] = useState<any>(() => {
    try {
      const saved = localStorage.getItem('glycoview_user') || sessionStorage.getItem('glycoview_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [authToken, setAuthToken] = useState<string | null>(() => {
    return localStorage.getItem('glycoview_token') || sessionStorage.getItem('glycoview_token');
  });

  const [metrics, setMetrics] = useState<Metrics>({});
  const [availableDays, setAvailableDays] = useState<{ date: string; low: number; target: number; high: number }[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [activeMenu, setActiveMenu] = useState('dashboard');
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    return localStorage.getItem('glycoview_sidebar_collapsed') === 'true';
  });

  const toggleSidebar = () => {
    setSidebarCollapsed(prev => {
      const next = !prev;
      localStorage.setItem('glycoview_sidebar_collapsed', String(next));
      return next;
    });
  };

  const handleLoginSuccess = (user: any, token: string) => {
    setCurrentUser(user);
    setAuthToken(token);
  };

  const handleLogout = () => {
    localStorage.removeItem('glycoview_token');
    localStorage.removeItem('glycoview_user');
    sessionStorage.removeItem('glycoview_token');
    sessionStorage.removeItem('glycoview_user');
    setCurrentUser(null);
    setAuthToken(null);
  };

  // Load available days from DB
  useEffect(() => {
    if (!authToken) return;
    fetch(`${API_BASE_URL}/api/v1/analysis/days`)
      .then(res => res.json())
      .then(days => setAvailableDays(days))
      .catch(err => console.error("Error fetching available days:", err));
  }, [authToken]);

  // Load metrics (global or for selected day)
  useEffect(() => {
    if (!authToken) return;
    const url = selectedDate
      ? `${API_BASE_URL}/api/v1/analysis/metrics?date=${selectedDate}`
      : `${API_BASE_URL}/api/v1/analysis/metrics`;

    fetch(url)
      .then(res => res.json())
      .then(data => setMetrics(data))
      .catch(err => console.error("Error fetching metrics:", err));
  }, [selectedDate, authToken]);

  // If not authenticated, render Login Page
  if (!authToken || !currentUser) {
    return <LoginView onLoginSuccess={handleLoginSuccess} />;
  }

  const selectedDateFormatted = selectedDate
    ? new Date(selectedDate).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
    : null;

  return (
    <>
      <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
        <div className="brand" style={{ display: 'flex', alignItems: 'center', justifyContent: sidebarCollapsed ? 'center' : 'space-between', marginBottom: '1.5rem', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', overflow: 'hidden' }}>
            <Activity className="w-6 h-6" style={{ color: "var(--accent)", flexShrink: 0 }} />
            {!sidebarCollapsed && <span className="brand-text">GlycoView</span>}
          </div>
          <button
            onClick={toggleSidebar}
            title={sidebarCollapsed ? "Agrandir le menu (Sidebar)" : "Réduire le menu (Sidebar)"}
            className="sidebar-toggle-btn"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              padding: '0.35rem',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s ease',
            }}
          >
            {sidebarCollapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
          </button>
        </div>
        <nav className="nav-menu">
          <div
            className={`nav-item ${activeMenu === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveMenu('dashboard')}
            title="Dashboard (Aperçu Général)"
          >
            <LayoutDashboard className="w-5 h-5" style={{ flexShrink: 0 }} />
            {!sidebarCollapsed && <span className="nav-text">Dashboard</span>}
          </div>
          <div
            className={`nav-item ${activeMenu === 'training_data' ? 'active' : ''}`}
            onClick={() => setActiveMenu('training_data')}
            title="Données d'Entraînement ML (Extraction & Formatage)"
          >
            <Database className="w-5 h-5" style={{ flexShrink: 0 }} />
            {!sidebarCollapsed && <span className="nav-text">Données d'Entraînement</span>}
          </div>
          <div
            className={`nav-item ${activeMenu === 'analysis' ? 'active' : ''}`}
            onClick={() => setActiveMenu('analysis')}
            title="Analyses Statistiques (J3)"
          >
            <LineChart className="w-5 h-5" style={{ flexShrink: 0 }} />
            {!sidebarCollapsed && <span className="nav-text">Analyses (J3)</span>}
          </div>
          <div
            className={`nav-item ${activeMenu === 'prediction' ? 'active' : ''}`}
            onClick={() => setActiveMenu('prediction')}
            title="Modèles de Prédictions (J4)"
          >
            <BrainCircuit className="w-5 h-5" style={{ flexShrink: 0 }} />
            {!sidebarCollapsed && <span className="nav-text">Prédictions (J4)</span>}
          </div>
          <div
            className={`nav-item ${activeMenu === 'digital_twin' ? 'active' : ''}`}
            onClick={() => setActiveMenu('digital_twin')}
            title="Jumeau Numérique Physiologique (J6)"
          >
            <Cpu className="w-5 h-5" style={{ flexShrink: 0 }} />
            {!sidebarCollapsed && <span className="nav-text">Jumeau Numérique (J6)</span>}
          </div>
          <div
            className={`nav-item ${activeMenu === 'rl_agent' ? 'active' : ''}`}
            onClick={() => setActiveMenu('rl_agent')}
            title="Jumeau & Agent RL (Phase 5 - Mode Ombre)"
          >
            <Zap className="w-5 h-5" style={{ flexShrink: 0, color: activeMenu === 'rl_agent' ? '#fff' : '#10b981' }} />
            {!sidebarCollapsed && <span className="nav-text" style={{ color: activeMenu === 'rl_agent' ? '#fff' : '#10b981', fontWeight: '700' }}>Jumeau & Agent RL</span>}
          </div>
          <div style={{ flex: 1 }}></div>

          {/* User profile & Logout footer */}
          <div style={{
            background: 'rgba(15, 23, 42, 0.6)',
            border: '1px solid rgba(148, 163, 184, 0.12)',
            borderRadius: '12px',
            padding: sidebarCollapsed ? '0.5rem 0.2rem' : '0.85rem',
            marginTop: 'auto',
            display: 'flex',
            flexDirection: 'column',
            alignItems: sidebarCollapsed ? 'center' : 'stretch',
            gap: '0.4rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', justifyContent: sidebarCollapsed ? 'center' : 'flex-start' }}
                 title={sidebarCollapsed ? `${currentUser?.name || 'Ahmed DANY'} (${currentUser?.role || 'Patient Investigé'})` : undefined}>
              <div style={{
                width: '34px',
                height: '34px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, #6366f1, #38bdf8)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: '700',
                color: '#fff',
                fontSize: '0.85rem',
                flexShrink: 0
              }}>
                {currentUser?.name ? currentUser.name.split(' ').map((n: string) => n[0]).slice(0, 2).join('') : 'AD'}
              </div>
              {!sidebarCollapsed && (
                <div style={{ overflow: 'hidden', flex: 1 }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: '700', color: '#f8fafc', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                    {currentUser?.name || 'Ahmed DANY'}
                  </div>
                  <div style={{ fontSize: '0.68rem', color: '#38bdf8', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                    {currentUser?.role || 'Patient Investigé'}
                  </div>
                  <div style={{ fontSize: '0.62rem', color: '#64748b', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                    Dr : MC Lhoussaine Abainou
                  </div>
                </div>
              )}
            </div>

            <button
              onClick={handleLogout}
              title="Déconnexion"
              style={{
                width: sidebarCollapsed ? '34px' : '100%',
                height: sidebarCollapsed ? '34px' : 'auto',
                marginTop: sidebarCollapsed ? '0.2rem' : '0.65rem',
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.25)',
                color: '#f87171',
                borderRadius: '8px',
                padding: sidebarCollapsed ? '0' : '0.4rem',
                fontSize: '0.75rem',
                fontWeight: '600',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.4rem',
                transition: 'all 0.2s ease'
              }}
            >
              <LogOut style={{ width: '13px', height: '13px', flexShrink: 0 }} />
              {!sidebarCollapsed && <span>Déconnexion</span>}
            </button>
          </div>
        </nav>
      </aside>

      <div className={`main-wrapper ${sidebarCollapsed ? 'expanded-content' : ''}`}>
        <header className="header">
          <div className="header-title" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {activeMenu === 'dashboard' && (
              selectedDate ? (
                <span>Journée du <strong style={{ color: '#60a5fa', textTransform: 'capitalize' }}>{selectedDateFormatted}</strong></span>
              ) : (
                <span>Aperçu Général <small style={{ color: '#10b981', fontSize: '0.8rem', fontWeight: 'normal' }}>● En direct</small></span>
              )
            )}
            {activeMenu === 'training_data' && 'Données d\'Entraînement ML (Extraction & Formatage)'}
            {activeMenu === 'analysis' && 'Analyses Statistiques'}
            {activeMenu === 'prediction' && 'Modèles de Prédiction'}
            {activeMenu === 'digital_twin' && 'Jumeau Numérique Physiologique (J6)'}
            {activeMenu === 'rl_agent' && (
              <span>Jumeau Numérique & Agent RL <small style={{ color: '#10b981', fontSize: '0.8rem', fontWeight: 'bold' }}>● Phase 5 Mode Ombre</small></span>
            )}
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            {activeMenu === 'dashboard' && metrics.mean !== undefined && (
              <span>Moyenne : {metrics.mean} mg/dL</span>
            )}
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              fontSize: '0.75rem',
              color: '#38bdf8',
              background: 'rgba(56, 189, 248, 0.1)',
              padding: '0.2rem 0.6rem',
              borderRadius: '12px',
              border: '1px solid rgba(56, 189, 248, 0.2)'
            }}>
              <ShieldCheck style={{ width: '12px', height: '12px' }} /> Connecté : {currentUser?.username || 'admin'}
            </span>
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

          {activeMenu === 'training_data' && (
            <TrainingDataView />
          )}

          {activeMenu === 'prediction' && (
            <PredictionView />
          )}

          {activeMenu === 'digital_twin' && (
            <DigitalTwinView />
          )}

          {activeMenu === 'rl_agent' && (
            <RLAgentView />
          )}
        </main>
      </div>
    </>
  );
}

export default App;
