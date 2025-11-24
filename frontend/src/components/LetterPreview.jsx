import React from 'react';

function LetterPreview({ letter }) {
  if (!letter) {
    return <p className="muted">No letter generated yet.</p>;
  }

  const handleDownload = () => {
    const blob = new Blob([letter.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = letter.letter_id + '.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="letter-preview">
      <pre>{letter.content}</pre>
      <button className="secondary" onClick={handleDownload}>
        Download Letter
      </button>
    </div>
  );
}

export default LetterPreview;
