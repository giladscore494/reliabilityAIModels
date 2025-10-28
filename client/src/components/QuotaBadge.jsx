export default function QuotaBadge({ quota }) {
  if (!quota) return null;

  const userLeft = quota.user_left_today;
  const globalLeft = quota.global_left_today;

  const getUserColor = (left) => {
    if (left === 0) return '#ff4444';
    if (left <= 2) return '#ffaa00';
    return '#44ff44';
  };

  const getGlobalColor = (left) => {
    if (left < 100) return '#ff4444';
    if (left < 500) return '#ffaa00';
    return '#44ff44';
  };

  return (
    <div style={{ 
      display: 'flex',
      gap: '1rem',
      alignItems: 'center'
    }}>
      <div style={{ 
        padding: '0.5rem 1rem',
        background: '#1a1a1a',
        borderRadius: '6px',
        border: `2px solid ${getUserColor(userLeft)}`,
        fontSize: '0.9rem',
        textAlign: 'center'
      }}>
        <div style={{ opacity: 0.7, fontSize: '0.75rem', marginBottom: '0.2rem' }}>
          Your Quota
        </div>
        <div style={{ 
          fontWeight: 'bold',
          color: getUserColor(userLeft),
          fontSize: '1.1rem'
        }}>
          {userLeft} / 5
        </div>
      </div>

      <div style={{ 
        padding: '0.5rem 1rem',
        background: '#1a1a1a',
        borderRadius: '6px',
        border: `2px solid ${getGlobalColor(globalLeft)}`,
        fontSize: '0.9rem',
        textAlign: 'center'
      }}>
        <div style={{ opacity: 0.7, fontSize: '0.75rem', marginBottom: '0.2rem' }}>
          Global Quota
        </div>
        <div style={{ 
          fontWeight: 'bold',
          color: getGlobalColor(globalLeft),
          fontSize: '1.1rem'
        }}>
          {globalLeft} / 1000
        </div>
      </div>
    </div>
  );
}
