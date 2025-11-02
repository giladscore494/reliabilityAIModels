export default function IssuesCostsCard({ issues, issuesWithCosts, avgCost }) {
  const hasIssues = issues && issues.length > 0;
  const hasCosts = issuesWithCosts && issuesWithCosts.length > 0;
  const hasAvgCost = avgCost !== null && avgCost !== undefined && avgCost !== '';

  if (!hasIssues && !hasCosts && !hasAvgCost) {
    return (
      <div style={{ 
        background: '#1a1a1a', 
        padding: '1.5rem', 
        borderRadius: '8px',
        border: '1px solid #333',
        textAlign: 'right'
      }}>
        <h3 style={{ marginBottom: '1rem' }}>🔧 תקלות ועלויות</h3>
        <p style={{ opacity: 0.7 }}>אין מידע תקלות/עלויות שמור למקרה זה.</p>
      </div>
    );
  }

  return (
    <div style={{ 
      background: '#1a1a1a', 
      padding: '1.5rem', 
      borderRadius: '8px',
      border: '1px solid #333'
    }}>
      <h3 style={{ marginBottom: '1rem', textAlign: 'right' }}>🔧 תקלות ועלויות</h3>
      
      {hasIssues && (
        <div style={{ marginBottom: hasCosts ? '1.5rem' : '0', textAlign: 'right' }}>
          <h4 style={{ fontSize: '0.9rem', opacity: 0.8, marginBottom: '0.5rem' }}>
            תקלות נפוצות:
          </h4>
          <ul style={{ 
            listStyle: 'none', 
            padding: 0, 
            margin: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: '0.4rem'
          }}>
            {issues.map((issue, idx) => (
              issue && (
                <li key={idx} style={{ 
                  padding: '0.5rem',
                  background: '#2a2a2a',
                  borderRadius: '4px',
                  borderRight: '3px solid #646cff'
                }}>
                  • {issue}
                </li>
              )
            ))}
          </ul>
        </div>
      )}

      {hasCosts && (
        <div style={{ textAlign: 'right' }}>
          <h4 style={{ fontSize: '0.9rem', opacity: 0.8, marginBottom: '0.5rem' }}>
            💰 עלויות תיקון (אינדיקטיבי):
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {issuesWithCosts.map((item, idx) => {
              if (!item || typeof item !== 'object') return null;
              
              const issue = item.issue || '';
              const cost = item.avg_cost_ILS || item.cost || '';
              const severity = item.severity || '';
              const source = item.source || '';
              
              const severityColor = 
                severity === 'גבוה' ? '#ff4444' :
                severity === 'בינוני' ? '#ffaa00' :
                severity === 'נמוך' ? '#44ff44' :
                '#aaaaaa';
              
              let costText = '';
              try {
                costText = cost ? `כ-${parseInt(cost).toLocaleString()} ₪` : '';
              } catch {
                costText = cost ? `${cost}` : '';
              }
              
              return (
                <div key={idx} style={{ 
                  padding: '0.7rem',
                  background: '#2a2a2a',
                  borderRadius: '4px',
                  borderRight: `3px solid ${severityColor}`
                }}>
                  <div style={{ fontWeight: 'bold', marginBottom: '0.3rem' }}>
                    {issue}
                  </div>
                  <div style={{ 
                    fontSize: '0.85rem', 
                    opacity: 0.8,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexDirection: 'row-reverse'
                  }}>
                    {costText && <span style={{ color: '#646cff' }}>{costText}</span>}
                    {severity && (
                      <span style={{ 
                        fontSize: '0.75rem',
                        padding: '2px 6px',
                        borderRadius: '3px',
                        background: severityColor,
                        color: '#000'
                      }}>
                        חומרה: {severity}
                      </span>
                    )}
                  </div>
                  {source && (
                    <div style={{ fontSize: '0.75rem', opacity: 0.6, marginTop: '0.3rem' }}>
                      מקור: {source}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {hasAvgCost && (
        <div style={{ 
          marginTop: '1rem',
          padding: '0.8rem',
          background: '#2a2a2a',
          borderRadius: '4px',
          textAlign: 'center',
          borderTop: '2px solid #646cff'
        }}>
          <span style={{ opacity: 0.8 }}>עלות תחזוקה ממוצעת: </span>
          <span style={{ fontWeight: 'bold', color: '#646cff', fontSize: '1.1rem' }}>
            {typeof avgCost === 'number' ? `כ-${avgCost.toLocaleString()} ₪` : avgCost}
          </span>
        </div>
      )}
    </div>
  );
}
