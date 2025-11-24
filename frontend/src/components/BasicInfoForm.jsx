import React, { useState } from 'react';

function BasicInfoForm({ onSubmit, loading }) {
  const [form, setForm] = useState({
    name: '',
    dob: '',
    phone: '',
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(form);
  };

  return (
    <form onSubmit={handleSubmit} className="form">
      <label>
        Name
        <input
          name="name"
          value={form.name}
          onChange={handleChange}
          placeholder="John Doe"
          required
        />
      </label>
      <label>
        Date of Admission
        <input
          name="doa"
          type="date"
          value={form.doa}
          onChange={handleChange}
          required
        />
      </label>
      <label>
        Billing Amount
        <input
          name="Amount"
          value={form.amount}
          onChange={handleChange}
          placeholder="18856.281305978155"
          required
        />
      </label>
      <button className="primary" type="submit" disabled={loading}>
        {loading ? 'Saving…' : 'Save & View Coverage'}
      </button>
    </form>
  );
}

export default BasicInfoForm;
