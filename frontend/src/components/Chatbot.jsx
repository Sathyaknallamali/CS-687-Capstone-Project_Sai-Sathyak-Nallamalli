import React, { useState } from 'react';
import { chatbotMessage } from '../api.js';

function Chatbot({ phone }) {
  const [input, setInput] = useState('');
  const [conversation, setConversation] = useState([]);

  const sendMessage = async () => {
    if (!input.trim()) return;
    const userMsg = { from: 'user', text: input };
    setConversation((c) => [...c, userMsg]);
    setInput('');

    if (!phone) {
      setConversation((c) => [
        ...c,
        { from: 'bot', text: 'Please enter your details first so I can help.' },
      ]);
      return;
    }

    try {
      const res = await chatbotMessage(phone, userMsg.text);
      setConversation((c) => [...c, { from: 'bot', text: res.reply }]);
    } catch (e) {
      console.error(e);
      setConversation((c) => [
        ...c,
        { from: 'bot', text: 'Sorry, something went wrong.' },
      ]);
    }
  };

  const handleKey = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="chatbot">
      <div className="chat-window">
        {conversation.map((m, idx) => (
          <div key={idx} className={m.from === 'user' ? 'msg user' : 'msg bot'}>
            {m.text}
          </div>
        ))}
        {conversation.length === 0 && (
          <p className="muted">
            Ask things like: “Is metformin covered?”, “What does my plan cover?”
          </p>
        )}
      </div>
      <div className="chat-input">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Type your question…"
        />
        <button className="primary" onClick={sendMessage}>
          Send
        </button>
      </div>
    </div>
  );
}

export default Chatbot;
