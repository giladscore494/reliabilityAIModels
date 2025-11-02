import { Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import http from '../api/http';

export default function Dashboard() {
  const [quota, setQuota] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch quota on mount
    http.get('/v1/quota')
      .then(res => {
        setQuota(res.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to fetch quota:', err);
        setLoading(false);
      });
  }, []);

  return (
    <div className="container">
      <header style={{ marginBottom: '3rem', textAlign: 'center' }}>
        <h1>🚗 Car Reliability Analyzer</h1>
        <p style={{ opacity: 0.7, marginTop: '0.5rem' }}>בדיקת אמינות רכב בישראל</p>
      </header>

      {!loading && quota && (
        <div style={{ 
          background: '#1a1a1a', 
          padding: '1.5rem', 
          borderRadius: '8px', 
          marginBottom: '2rem',
          textAlign: 'center'
        }}>
          <h3>Quota Status</h3>
          <p>Your remaining checks today: {quota.user_left_today}</p>
          <p>Global remaining checks today: {quota.global_left_today}</p>
        </div>
      )}

      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: '1.5rem',
        marginTop: '2rem'
      }}>
        <Link to="/analyze" style={{ textDecoration: 'none' }}>
          <div style={{ 
            background: '#1a1a1a', 
            padding: '2rem', 
            borderRadius: '8px',
            border: '1px solid transparent',
            transition: 'border-color 0.3s'
          }} 
          onMouseEnter={(e) => e.currentTarget.style.borderColor = '#646cff'}
          onMouseLeave={(e) => e.currentTarget.style.borderColor = 'transparent'}
          >
            <h2>🔍 Analyze</h2>
            <p style={{ opacity: 0.7, marginTop: '0.5rem' }}>Check car reliability</p>
          </div>
        </Link>

        <Link to="/history" style={{ textDecoration: 'none' }}>
          <div style={{ 
            background: '#1a1a1a', 
            padding: '2rem', 
            borderRadius: '8px',
            border: '1px solid transparent',
            transition: 'border-color 0.3s'
          }}
          onMouseEnter={(e) => e.currentTarget.style.borderColor = '#646cff'}
          onMouseLeave={(e) => e.currentTarget.style.borderColor = 'transparent'}
          >
            <h2>📚 History</h2>
            <p style={{ opacity: 0.7, marginTop: '0.5rem' }}>View past analyses</p>
          </div>
        </Link>

        <Link to="/roi" style={{ textDecoration: 'none' }}>
          <div style={{ 
            background: '#1a1a1a', 
            padding: '2rem', 
            borderRadius: '8px',
            border: '1px solid transparent',
            transition: 'border-color 0.3s'
          }}
          onMouseEnter={(e) => e.currentTarget.style.borderColor = '#646cff'}
          onMouseLeave={(e) => e.currentTarget.style.borderColor = 'transparent'}
          >
            <h2>💰 ROI Calculator</h2>
            <p style={{ opacity: 0.7, marginTop: '0.5rem' }}>Calculate future value</p>
          </div>
        </Link>

        <Link to="/leads" style={{ textDecoration: 'none' }}>
          <div style={{ 
            background: '#1a1a1a', 
            padding: '2rem', 
            borderRadius: '8px',
            border: '1px solid transparent',
            transition: 'border-color 0.3s'
          }}
          onMouseEnter={(e) => e.currentTarget.style.borderColor = '#646cff'}
          onMouseLeave={(e) => e.currentTarget.style.borderColor = 'transparent'}
          >
            <h2>📞 Get Quote</h2>
            <p style={{ opacity: 0.7, marginTop: '0.5rem' }}>Insurance, financing & more</p>
          </div>
        </Link>
      </div>
    </div>
  );
}
