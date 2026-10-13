import React, { useState } from 'react';
import { Activity, Lock, User, Eye, EyeOff, ShieldCheck, ArrowRight, AlertCircle } from 'lucide-react';
import { API_BASE_URL } from '../config';

interface LoginViewProps {
  onLoginSuccess: (user: any, token: string) => void;
}

export default function LoginView({ onLoginSuccess }: LoginViewProps) {
  const [username, setUsername] = useState('dany');
  const [password, setPassword] = useState('glycoview2026');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Échec de l'authentification. Identifiants incorrects.");
      }

      if (rememberMe) {
        localStorage.setItem('glycoview_token', data.token);
        localStorage.setItem('glycoview_user', JSON.stringify(data.user));
      } else {
        sessionStorage.setItem('glycoview_token', data.token);
        sessionStorage.setItem('glycoview_user', JSON.stringify(data.user));
      }

      onLoginSuccess(data.user, data.token);
    } catch (err: any) {
      setError(err.message || "Erreur de connexion au serveur.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'radial-gradient(circle at 50% 20%, rgba(99, 102, 241, 0.15) 0%, rgba(15, 23, 42, 0.98) 70%)',
      padding: '1.5rem',
      fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Decorative ambient background lights */}
      <div style={{
        position: 'absolute',
        top: '-10%',
        left: '20%',
        width: '450px',
        height: '450px',
        borderRadius: '50%',
        background: 'rgba(99, 102, 241, 0.12)',
        filter: 'blur(120px)',
        pointerEvents: 'none'
      }} />
      <div style={{
        position: 'absolute',
        bottom: '-10%',
        right: '20%',
        width: '400px',
        height: '400px',
        borderRadius: '50%',
        background: 'rgba(56, 189, 248, 0.12)',
        filter: 'blur(100px)',
        pointerEvents: 'none'
      }} />

      <div style={{
        width: '100%',
        maxWidth: '460px',
        background: 'rgba(30, 41, 59, 0.75)',
        backdropFilter: 'blur(20px)',
        border: '1px solid rgba(148, 163, 184, 0.15)',
        borderRadius: '24px',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 30px rgba(99, 102, 241, 0.15)',
        padding: '2.5rem',
        zIndex: 10,
        position: 'relative'
      }}>
        {/* Header Protocol Badge */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.25rem' }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.45rem',
            background: 'rgba(56, 189, 248, 0.1)',
            border: '1px solid rgba(56, 189, 248, 0.25)',
            color: '#38bdf8',
            padding: '0.35rem 0.85rem',
            borderRadius: '20px',
            fontSize: '0.75rem',
            fontWeight: '600'
          }}>
            <ShieldCheck style={{ width: '14px', height: '14px' }} />
            Protocole AAPS-DT Pilot v1.0 • HM Oued Eddahab
          </div>
        </div>

        {/* Brand Icon & Title */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            width: '64px',
            height: '64px',
            background: 'linear-gradient(135deg, #6366f1 0%, #38bdf8 100%)',
            borderRadius: '18px',
            margin: '0 auto 1rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 10px 25px rgba(99, 102, 241, 0.35)'
          }}>
            <Activity style={{ width: '32px', height: '32px', color: '#fff' }} />
          </div>
          <h1 style={{
            fontSize: '1.75rem',
            fontWeight: '800',
            color: '#f8fafc',
            letterSpacing: '-0.025em',
            margin: 0
          }}>
            Glyco<span style={{ color: '#38bdf8' }}>View</span>
          </h1>
          <p style={{
            fontSize: '0.85rem',
            color: '#94a3b8',
            marginTop: '0.5rem',
            lineHeight: 1.4
          }}>
            Portail d'Analyse Prédictive & Jumeau Numérique CGM
          </p>
        </div>

        {/* Error notification */}
        {error && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '12px',
            padding: '0.75rem 1rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.65rem',
            color: '#f87171',
            fontSize: '0.85rem',
            marginBottom: '1.5rem',
            animation: 'fadeIn 0.3s ease'
          }}>
            <AlertCircle style={{ width: '18px', height: '18px', flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Username */}
          <div>
            <label style={{
              display: 'block',
              fontSize: '0.8rem',
              fontWeight: '600',
              color: '#cbd5e1',
              marginBottom: '0.45rem'
            }}>
              Identifiant / Utilisateur
            </label>
            <div style={{ position: 'relative' }}>
              <div style={{
                position: 'absolute',
                left: '14px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: '#64748b'
              }}>
                <User style={{ width: '18px', height: '18px' }} />
              </div>
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Ex: admin ou dany"
                style={{
                  width: '100%',
                  background: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(148, 163, 184, 0.2)',
                  borderRadius: '12px',
                  padding: '0.75rem 1rem 0.75rem 2.75rem',
                  color: '#f8fafc',
                  fontSize: '0.9rem',
                  outline: 'none',
                  transition: 'all 0.2s ease',
                  boxSizing: 'border-box'
                }}
                onFocus={(e) => e.target.style.borderColor = '#6366f1'}
                onBlur={(e) => e.target.style.borderColor = 'rgba(148, 163, 184, 0.2)'}
              />
            </div>
          </div>

          {/* Password */}
          <div>
            <label style={{
              display: 'block',
              fontSize: '0.8rem',
              fontWeight: '600',
              color: '#cbd5e1',
              marginBottom: '0.45rem'
            }}>
              Mot de passe
            </label>
            <div style={{ position: 'relative' }}>
              <div style={{
                position: 'absolute',
                left: '14px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: '#64748b'
              }}>
                <Lock style={{ width: '18px', height: '18px' }} />
              </div>
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                style={{
                  width: '100%',
                  background: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(148, 163, 184, 0.2)',
                  borderRadius: '12px',
                  padding: '0.75rem 2.75rem 0.75rem 2.75rem',
                  color: '#f8fafc',
                  fontSize: '0.9rem',
                  outline: 'none',
                  transition: 'all 0.2s ease',
                  boxSizing: 'border-box'
                }}
                onFocus={(e) => e.target.style.borderColor = '#6366f1'}
                onBlur={(e) => e.target.style.borderColor = 'rgba(148, 163, 184, 0.2)'}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: '#64748b',
                  cursor: 'pointer',
                  padding: '4px'
                }}
                tabIndex={-1}
              >
                {showPassword ? (
                  <EyeOff style={{ width: '18px', height: '18px' }} />
                ) : (
                  <Eye style={{ width: '18px', height: '18px' }} />
                )}
              </button>
            </div>
          </div>

          {/* Remember me & Quick credentials */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.8rem',
            color: '#94a3b8'
          }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                style={{ accentColor: '#6366f1', cursor: 'pointer' }}
              />
              Rester connecté
            </label>
          </div>

          {/* Quick preset selector */}
          <div style={{
            background: 'rgba(15, 23, 42, 0.5)',
            border: '1px solid rgba(148, 163, 184, 0.12)',
            borderRadius: '12px',
            padding: '0.65rem 0.75rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.45rem'
          }}>
            <span style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Connexion Rapide par Rôle :
            </span>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                type="button"
                onClick={() => {
                  setUsername('dany');
                  setPassword('glycoview2026');
                  setError(null);
                }}
                style={{
                  flex: 1,
                  background: username === 'dany' || username === 'admin' ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                  border: username === 'dany' || username === 'admin' ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid rgba(148, 163, 184, 0.15)',
                  color: '#38bdf8',
                  cursor: 'pointer',
                  borderRadius: '8px',
                  padding: '0.4rem',
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  textAlign: 'center',
                  transition: 'all 0.2s ease'
                }}
              >
                👤 Patient (Ahmed DANY)
              </button>

              <button
                type="button"
                onClick={() => {
                  setUsername('abainou');
                  setPassword('glycoview2026');
                  setError(null);
                }}
                style={{
                  flex: 1,
                  background: username === 'abainou' ? 'rgba(99, 102, 241, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                  border: username === 'abainou' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid rgba(148, 163, 184, 0.15)',
                  color: '#a5b4fc',
                  cursor: 'pointer',
                  borderRadius: '8px',
                  padding: '0.4rem',
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  textAlign: 'center',
                  transition: 'all 0.2s ease'
                }}
              >
                🩺 Médecin (MC Lhoussaine Abainou)
              </button>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            style={{
              background: 'linear-gradient(135deg, #6366f1 0%, #38bdf8 100%)',
              color: '#ffffff',
              border: 'none',
              borderRadius: '12px',
              padding: '0.85rem',
              fontWeight: '700',
              fontSize: '0.95rem',
              cursor: loading ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              boxShadow: '0 4px 15px rgba(99, 102, 241, 0.4)',
              transition: 'all 0.2s ease',
              marginTop: '0.2rem'
            }}
          >
            {loading ? (
              <span>Vérification des accès...</span>
            ) : (
              <>
                <span>Se connecter</span>
                <ArrowRight style={{ width: '18px', height: '18px' }} />
              </>
            )}
          </button>
        </form>

        {/* Clinical Note Footer */}
        <div style={{
          marginTop: '1.75rem',
          paddingTop: '1rem',
          borderTop: '1px solid rgba(148, 163, 184, 0.1)',
          textAlign: 'center'
        }}>
          <p style={{
            margin: 0,
            fontSize: '0.73rem',
            color: '#94a3b8',
            lineHeight: 1.5
          }}>
            Patient : <strong style={{ color: '#38bdf8' }}>Ahmed DANY</strong>
            <br />
            Investigateur Principal : <strong style={{ color: '#a5b4fc' }}>Médecin Commandant Lhoussaine Abainou</strong>
            <br />
            <span style={{ fontSize: '0.68rem', color: '#64748b' }}>Hôpital Militaire Oued Eddahab - Agadir</span>
          </p>
        </div>
      </div>
    </div>
  );
}
