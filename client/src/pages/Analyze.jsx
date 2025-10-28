import { useState } from 'react';
import { Link } from 'react-router-dom';
import http from '../api/http';
import ReliabilityForm from '../components/ReliabilityForm';
import ScoreBreakdownCard from '../components/ScoreBreakdownCard';
import IssuesCostsCard from '../components/IssuesCostsCard';
import ChecksCard from '../components/ChecksCard';
import CompetitorsCard from '../components/CompetitorsCard';
import QuotaBadge from '../components/QuotaBadge';

export default function Analyze() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleAnalyze = async (formData) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await http.post('/v1/analyze', formData);
      setResult(response.data);
    } catch (err) {
      if (err.response?.status === 429) {
        setError('Daily limit reached. Please try again tomorrow.');
      } else if (err.response?.status === 503) {
        setError('Service temporarily unavailable. Please try again later.');
      } else {
        setError('Failed to analyze. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <header style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>🔍 Reliability Analysis</h1>
          <Link to="/" style={{ color: '#646cff', textDecoration: 'none' }}>← Back to Dashboard</Link>
        </div>
        {result && <QuotaBadge quota={result.quota} />}
      </header>

      <ReliabilityForm onSubmit={handleAnalyze} loading={loading} />

      {error && (
        <div style={{ 
          background: '#ff4444', 
          color: 'white', 
          padding: '1rem', 
          borderRadius: '8px', 
          marginTop: '2rem' 
        }}>
          ❌ {error}
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', marginTop: '2rem' }}>
          <p>⏳ Analyzing... Please wait...</p>
        </div>
      )}

      {result && (
        <div style={{ marginTop: '2rem' }}>
          {/* Score display */}
          <div style={{ 
            background: '#1a1a1a', 
            padding: '2rem', 
            borderRadius: '8px', 
            marginBottom: '2rem',
            textAlign: 'center'
          }}>
            <h2>Reliability Score</h2>
            <div style={{ fontSize: '4rem', fontWeight: 'bold', color: '#646cff' }}>
              {result.result.base_score_calculated} / 100
            </div>
            {result.km_warn && (
              <p style={{ color: '#ffaa00', marginTop: '1rem' }}>
                ⚠️ Mileage range differs from cached data
              </p>
            )}
            {result.mileage_note && (
              <p style={{ color: '#aaaaff', marginTop: '0.5rem' }}>
                ℹ️ {result.mileage_note}
              </p>
            )}
            <p style={{ opacity: 0.7, marginTop: '1rem' }}>
              Source: {result.source === 'cache' ? '📚 Cache' : '🤖 AI Model'}
              {result.used_fallback && ' (without sub-model)'}
            </p>
            {result.result.reliability_summary && (
              <p style={{ marginTop: '1rem', textAlign: 'right' }}>
                {result.result.reliability_summary}
              </p>
            )}
          </div>

          {/* Tabs for detailed info */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
            <ScoreBreakdownCard breakdown={result.result.score_breakdown} />
            <IssuesCostsCard 
              issues={result.result.common_issues} 
              issuesWithCosts={result.result.issues_with_costs}
              avgCost={result.result.avg_repair_cost_ILS}
            />
            <ChecksCard checks={result.result.recommended_checks} />
            <CompetitorsCard competitors={result.result.common_competitors_brief} />
          </div>

          {/* Sources */}
          {result.result.sources && result.result.sources.length > 0 && (
            <div style={{ 
              background: '#1a1a1a', 
              padding: '1.5rem', 
              borderRadius: '8px', 
              marginTop: '1.5rem' 
            }}>
              <h3>Sources</h3>
              <ul style={{ marginTop: '0.5rem', paddingRight: '1.5rem' }}>
                {result.result.sources.map((source, idx) => (
                  <li key={idx} style={{ marginBottom: '0.3rem' }}>{source}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
