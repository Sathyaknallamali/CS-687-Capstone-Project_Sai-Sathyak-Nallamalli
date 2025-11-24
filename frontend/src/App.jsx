import React, { useState } from 'react';
import BasicInfoForm from './components/BasicInfoForm.jsx';
import CoverageView from './components/CoverageView.jsx';
import Chatbot from './components/Chatbot.jsx';
import LetterPreview from './components/LetterPreview.jsx';
import { registerPatient, fetchDashboard, generateLetter } from './api.js';

function App() {
  const [patient, setPatient] = useState(null);
  const [plan, setPlan] = useState(null);
  const [usage, setUsage] = useState(null);
  const [latestLetter, setLatestLetter] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleRegister = async (form) => {
    try {
      setError(null);
      setLoading(true);
      const res = await registerPatient(form);
      setPatient(res.patient);
      setPlan(res.plan);
      const dash = await fetchDashboard(res.patient.phone);
      setUsage(dash.usage_summary);
      setLatestLetter(dash.latest_letter);
    } catch (e) {
      console.error(e);
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    if (!patient?.phone) return;
    try {
      const dash = await fetchDashboard(patient.phone);
      setPlan(dash.plan);
      setUsage(dash.usage_summary);
      setLatestLetter(dash.latest_letter);
    } catch (e) {
      console.error(e);
    }
  };

  const handleGenerateLetter = async (type) => {
    if (!patient?.phone) return;
    setLoading(true);
    try {
      const letter = await generateLetter(patient.phone, type);
      setLatestLetter(letter);
    } catch (e) {
      console.error(e);
      setError('Failed to generate letter.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="header">
        <h1>MediSecure AI – Insurance Helper</h1>
        <p>Simple coverage view & AI assistance for seniors.</p>
      </header>

      <main className="layout">
        <section className="card">
          <h2>1. Basic Information</h2>
          <BasicInfoForm onSubmit={handleRegister} loading={loading} />
          {error && <p className="error">{error}</p>}
        </section>

        <section className="card">
          <h2>2. Your Coverage</h2>
          <CoverageView
            patient={patient}
            plan={plan}
            usage={usage}
            onRefresh={handleRefresh}
          />
          <button
            className="primary"
            disabled={!patient || loading}
            onClick={() => handleGenerateLetter('coverage_summary')}
          >
            Generate Coverage Letter
          </button>
        </section>

        <section className="card">
          <h2>3. AI Assistant</h2>
          <Chatbot phone={patient?.phone} />
        </section>

        <section className="card full">
          <h2>Latest Letter</h2>
          <LetterPreview letter={latestLetter} />
        </section>
      </main>
    </div>
  );
}

export default App;
