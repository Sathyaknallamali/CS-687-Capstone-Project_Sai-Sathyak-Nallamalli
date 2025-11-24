const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function registerPatient(payload) {
  const res = await fetch(`${BASE_URL}/api/patient/register/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Register failed');
  return res.json();
}

export async function fetchDashboard(phone) {
  const res = await fetch(`${BASE_URL}/api/patient/${phone}/`);
  if (!res.ok) throw new Error('Dashboard fetch failed');
  return res.json();
}

export async function generateLetter(phone, letterType = 'coverage_summary') {
  const res = await fetch(`${BASE_URL}/api/letters/generate/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, letter_type: letterType }),
  });
  if (!res.ok) throw new Error('Letter generation failed');
  return res.json();
}

export async function chatbotMessage(phone, message) {
  const res = await fetch(`${BASE_URL}/api/chatbot/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, message }),
  });
  if (!res.ok) throw new Error('Chatbot failed');
  return res.json();
}
