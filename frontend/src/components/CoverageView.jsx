import React from 'react';

function CoverageView({ patient, plan, usage, onRefresh }) {
  if (!patient) {
    return <p className="muted">Enter your info to see your plan and usage.</p>;
  }

  return (
    <div>
      <p><strong>Name:</strong> {patient.name}</p>
      <p><strong>Plan:</strong> {plan?.plan_name}</p>
      <p><strong>Description:</strong> {plan?.description}</p>

      <h4>Usage</h4>
      {usage ? (
        <ul>
          <li>Visits used: {usage.visits}</li>
          <li>Estimated spend: ${usage.total_spend?.toFixed(2)}</li>
        </ul>
      ) : (
        <p className="muted">No usage data yet.</p>
      )}

      <button className="secondary" onClick={onRefresh}>
        Refresh
      </button>
    </div>
  );
}

export default CoverageView;
