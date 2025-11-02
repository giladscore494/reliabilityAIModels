import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import http from '../api/http';

export default function History() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const response = await http.get('/v1/history?limit=100&offset=0');
      setHistory(response.data.items);
      setLoading(false);
    } catch (err) {
      setError('Failed to load history');
      setLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      const response = await http.get('/v1/history/export.csv', {
        responseType: 'blob'
      });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `history_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      alert('Failed to export history');
    }
  };

  return (
    <div className="container">
      <header style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>📚 Analysis History</h1>
          <Link to="/" style={{ color: '#646cff', textDecoration: 'none' }}>← Back to Dashboard</Link>
        </div>
        {history.length > 0 && (
          <button onClick={handleExport}>Export CSV</button>
        )}
      </header>

      {loading && <p>Loading...</p>}
      
      {error && <p style={{ color: 'red' }}>{error}</p>}

      {!loading && history.length === 0 && (
        <div style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ opacity: 0.7 }}>No analysis history yet</p>
          <Link to="/analyze">
            <button style={{ marginTop: '1rem' }}>Start Analysis</button>
          </Link>
        </div>
      )}

      {history.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ 
            width: '100%', 
            borderCollapse: 'collapse',
            background: '#1a1a1a',
            borderRadius: '8px'
          }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #333' }}>
                <th style={{ padding: '1rem', textAlign: 'right' }}>Date</th>
                <th style={{ padding: '1rem', textAlign: 'right' }}>Make</th>
                <th style={{ padding: '1rem', textAlign: 'right' }}>Model</th>
                <th style={{ padding: '1rem', textAlign: 'right' }}>Year</th>
                <th style={{ padding: '1rem', textAlign: 'right' }}>Mileage</th>
                <th style={{ padding: '1rem', textAlign: 'right' }}>Score</th>
              </tr>
            </thead>
            <tbody>
              {history.map((item, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid #333' }}>
                  <td style={{ padding: '1rem', textAlign: 'right' }}>{item.date}</td>
                  <td style={{ padding: '1rem', textAlign: 'right' }}>{item.make}</td>
                  <td style={{ padding: '1rem', textAlign: 'right' }}>{item.model}</td>
                  <td style={{ padding: '1rem', textAlign: 'right' }}>{item.year}</td>
                  <td style={{ padding: '1rem', textAlign: 'right' }}>{item.mileage_range}</td>
                  <td style={{ padding: '1rem', textAlign: 'right' }}>
                    {item.base_score_calculated || 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
