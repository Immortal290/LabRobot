import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bot, Lock, User } from 'lucide-react';
import { GlassPanel } from '../components/GlassPanel';
import { useAuth } from '../context/AuthContext';

export const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const response = await fetch('http://localhost:8000/api/v1/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Invalid credentials');
      }

      const data = await response.json();
      
      // Fetch user profile using the token
      const profileResponse = await fetch('http://localhost:8000/api/v1/users/me', {
        headers: { 'Authorization': `Bearer ${data.access_token}` }
      });
      const profile = await profileResponse.json();

      login(data.access_token, profile);
      navigate(profile.role === 'Admin' ? '/admin' : '/user');
    } catch (err) {
      setError('Invalid credentials or server offline');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-center" style={{ minHeight: '100vh', padding: '20px' }}>
      <GlassPanel className="w-full max-w-md">
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <Bot size={48} color="var(--accent-cyan)" style={{ margin: '0 auto 1rem' }} />
          <h1 style={{ fontSize: '1.5rem', fontWeight: 600, color: 'var(--accent-cyan)' }}>
            LabRobot Secure Access
          </h1>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
            Enter your credentials to continue
          </p>
        </div>

        {error && (
          <div style={{ 
            background: 'rgba(239, 68, 68, 0.2)', 
            color: '#fca5a5', 
            padding: '12px', 
            borderRadius: '8px',
            marginBottom: '1rem',
            textAlign: 'center'
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ position: 'relative' }}>
            <User size={20} style={{ position: 'absolute', left: '12px', top: '14px', color: 'var(--text-secondary)' }} />
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="input-field"
              style={{ paddingLeft: '40px' }}
              required
            />
          </div>

          <div style={{ position: 'relative' }}>
            <Lock size={20} style={{ position: 'absolute', left: '12px', top: '14px', color: 'var(--text-secondary)' }} />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field"
              style={{ paddingLeft: '40px' }}
              required
            />
          </div>

          <button 
            type="submit" 
            className="btn btn-primary" 
            style={{ marginTop: '1rem' }}
            disabled={isLoading}
          >
            {isLoading ? 'Authenticating...' : 'Secure Login'}
          </button>
        </form>
      </GlassPanel>
    </div>
  );
};
