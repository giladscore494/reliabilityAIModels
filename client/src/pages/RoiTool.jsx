import { useState } from 'react';
import { Link } from 'react-router-dom';
import http from '../api/http';

export default function RoiTool() {
  const [formData, setFormData] = useState({
    make: '',
    model: '',
    year: new Date().getFullYear(),
    purchase_price: '',
    current_mileage: '',
    expected_annual_mileage: 15000
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await http.post('/v1/roi', {
        ...formData,
        year: parseInt(formData.year),
        purchase_price: parseInt(formData.purchase_price),
        current_mileage: parseInt(formData.current_mileage),
        expected_annual_mileage: parseInt(formData.expected_annual_mileage)
      });
      setResult(response.data);
    } catch (err) {
      setError('Failed to calculate ROI');
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
        <h1>💰 ROI Calculator</h1>
        <Link to="/" style={{ color: '#646cff', textDecoration: 'none' }}>← Back to Dashboard</Link>
      </header>

      <form onSubmit={handleSubmit} style={{ 
        background: '#1a1a1a', 
        padding: '2rem', 
        borderRadius: '8px',
        maxWidth: '600px'
      }}>
        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>Make</label>
          <input
            type="text"
            name="make"
            value={formData.make}
            onChange={handleChange}
            required
            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
          />
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>Model</label>
          <input
            type="text"
            name="model"
            value={formData.model}
            onChange={handleChange}
            required
            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
          />
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>Year</label>
          <input
            type="number"
            name="year"
            value={formData.year}
            onChange={handleChange}
            required
            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
          />
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>Purchase Price (₪)</label>
          <input
            type="number"
            name="purchase_price"
            value={formData.purchase_price}
            onChange={handleChange}
            required
            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
          />
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>Current Mileage (km)</label>
          <input
            type="number"
            name="current_mileage"
            value={formData.current_mileage}
            onChange={handleChange}
            required
            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
          />
        </div>

        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>Expected Annual Mileage (km)</label>
          <input
            type="number"
            name="expected_annual_mileage"
            value={formData.expected_annual_mileage}
            onChange={handleChange}
            required
            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
          />
        </div>

        <button type="submit" disabled={loading} style={{ width: '100%' }}>
          {loading ? 'Calculating...' : 'Calculate ROI'}
        </button>
      </form>

      {error && (
        <div style={{ color: 'red', marginTop: '1rem' }}>{error}</div>
      )}

      {result && (
        <div style={{ 
          background: '#1a1a1a', 
          padding: '2rem', 
          borderRadius: '8px',
          marginTop: '2rem',
          maxWidth: '600px'
        }}>
          <h2>Results</h2>
          <div style={{ display: 'grid', gap: '1rem', marginTop: '1rem' }}>
            <div>
              <h3>Estimated Values</h3>
              <p>1 Year: ₪{result.estimated_value_1y.toLocaleString()}</p>
              <p>3 Years: ₪{result.estimated_value_3y.toLocaleString()}</p>
              <p>5 Years: ₪{result.estimated_value_5y.toLocaleString()}</p>
            </div>
            <div>
              <h3>Total Cost of Ownership</h3>
              <p>1 Year: ₪{result.total_cost_of_ownership_1y.toLocaleString()}</p>
              <p>3 Years: ₪{result.total_cost_of_ownership_3y.toLocaleString()}</p>
              <p>5 Years: ₪{result.total_cost_of_ownership_5y.toLocaleString()}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
