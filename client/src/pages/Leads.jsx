import { useState } from 'react';
import { Link } from 'react-router-dom';
import http from '../api/http';

export default function Leads() {
  const [leadType, setLeadType] = useState('insurance');
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
    note: ''
  });
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await http.post('/v1/leads', {
        type: leadType,
        payload: formData
      });
      setSubmitted(true);
      setFormData({ name: '', phone: '', email: '', note: '' });
      setTimeout(() => setSubmitted(false), 3000);
    } catch (err) {
      setError('Failed to submit lead');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  return (
    <div className="container">
      <header style={{ marginBottom: '2rem' }}>
        <h1>📞 Get a Quote</h1>
        <Link to="/" style={{ color: '#646cff', textDecoration: 'none' }}>← Back to Dashboard</Link>
      </header>

      <div style={{ maxWidth: '600px' }}>
        <div style={{ marginBottom: '2rem' }}>
          <p>Select service type:</p>
          <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
            <button
              onClick={() => setLeadType('insurance')}
              style={{ 
                flex: 1,
                background: leadType === 'insurance' ? '#646cff' : '#1a1a1a'
              }}
            >
              Insurance
            </button>
            <button
              onClick={() => setLeadType('financing')}
              style={{ 
                flex: 1,
                background: leadType === 'financing' ? '#646cff' : '#1a1a1a'
              }}
            >
              Financing
            </button>
            <button
              onClick={() => setLeadType('dealer')}
              style={{ 
                flex: 1,
                background: leadType === 'dealer' ? '#646cff' : '#1a1a1a'
              }}
            >
              Dealer
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ 
          background: '#1a1a1a', 
          padding: '2rem', 
          borderRadius: '8px'
        }}>
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem' }}>Name</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
              style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
            />
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem' }}>Phone</label>
            <input
              type="tel"
              name="phone"
              value={formData.phone}
              onChange={handleChange}
              required
              style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
            />
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem' }}>Email</label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
            />
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem' }}>Note (optional)</label>
            <textarea
              name="note"
              value={formData.note}
              onChange={handleChange}
              rows={4}
              style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
            />
          </div>

          <button type="submit" disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Submitting...' : 'Submit'}
          </button>
        </form>

        {submitted && (
          <div style={{ 
            background: '#44ff44', 
            color: '#000', 
            padding: '1rem', 
            borderRadius: '8px', 
            marginTop: '1rem',
            textAlign: 'center'
          }}>
            ✓ Lead submitted successfully! We'll contact you soon.
          </div>
        )}

        {error && (
          <div style={{ 
            background: '#ff4444', 
            color: 'white', 
            padding: '1rem', 
            borderRadius: '8px', 
            marginTop: '1rem' 
          }}>
            ❌ {error}
          </div>
        )}
      </div>
    </div>
  );
}
