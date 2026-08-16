import { useEffect, useRef, useState } from "react";
import "./styles.css";

const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const suggestions = [
  { icon: "👟", title: "Find shoes", text: "Show me shoes under Rs. 3000" },
  { icon: "⭐", title: "Top rated", text: "Show top 3 shoes by rating" },
  { icon: "🏷️", title: "Best deals", text: "Show products with the biggest discounts" },
  { icon: "↩️", title: "Returns", text: "What is your return policy?" },
];

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isOnline, setIsOnline] = useState(false);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    checkBackend();
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function checkBackend() {
    try {
      const res = await fetch(`${API_URL}/health`);
      setIsOnline(res.ok);
    } catch {
      setIsOnline(false);
    }
  }

  async function sendMessage(value = input) {
    const query = value.trim();
    if (!query || loading) return;

    setMessages((old) => [...old, { role: "user", content: query }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || `Server returned ${res.status}`);
      }

      setMessages((old) => [
        ...old,
        {
          role: "assistant",
          content: data.answer || "I couldn't find an answer.",
          products: Array.isArray(data.products) ? data.products : [],
          route: data.route,
        },
      ]);
      setIsOnline(true);
    } catch (error) {
      console.error(error);
      setIsOnline(false);
      setMessages((old) => [
        ...old,
        {
          role: "error",
          content:
            error.message ||
            "Unable to connect to FastAPI. Start the backend on port 8000.",
        },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    sendMessage();
  }

  function clearChat() {
    setMessages([]);
    setTimeout(() => inputRef.current?.focus(), 50);
  }

  return (
    <div className="app-shell">
      <div className="background-glow glow-one" />
      <div className="background-glow glow-two" />
      <div className="background-grid" />

      <header className="topbar">
        <div className="brand-area">
          <div className="brand-logo">✦</div>
          <div>
            <div className="brand-name">Shop<span>AI</span></div>
            <div className="brand-subtitle">Intelligent shopping assistant</div>
          </div>
        </div>

        <div className="header-actions">
          <div className="online-status">
            <span className={`status-dot ${isOnline ? "online" : "offline"}`} />
            {isOnline ? "AI Online" : "Offline"}
          </div>
          <button className="header-icon-button" title="Wishlist" onClick={() => alert("Wishlist feature coming soon")}>♡</button>
          <button className="header-icon-button" title="Shopping cart" onClick={() => alert("Cart feature coming soon")}>🛒</button>
        </div>
      </header>

      <main className="main-content">
        {messages.length === 0 ? (
          <WelcomeScreen onSuggestion={sendMessage} />
        ) : (
          <section className="chat-section">
            <div className="chat-heading">
              <div>
                <div className="chat-heading-label">AI SHOPPING ASSISTANT</div>
                <h2>How can I help you shop?</h2>
              </div>
              <button className="clear-button" onClick={clearChat}>↻ New chat</button>
            </div>

            <div className="messages-container">
              {messages.map((message, index) => (
                <MessageBubble key={index} message={message} />
              ))}
              {loading && <TypingIndicator />}
              <div ref={endRef} />
            </div>
          </section>
        )}
      </main>

      <footer className="input-area">
        <div className="input-wrapper">
          <div className="input-top">
            <div className="input-label"><span>✦</span> AI SHOPPING</div>
            <div className="input-hint">Enter to send</div>
          </div>

          <form className="chat-form" onSubmit={handleSubmit}>
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about products, prices, discounts, returns..."
              disabled={loading}
              autoComplete="off"
            />
            <button className={`send-button ${input.trim() ? "active" : ""}`} disabled={!input.trim() || loading}>
              {loading ? <span className="button-spinner" /> : "➤"}
            </button>
          </form>
        </div>
        <div className="footer-note">✦ AI-generated responses based on your product database and store knowledge.</div>
      </footer>
    </div>
  );
}

function WelcomeScreen({ onSuggestion }) {
  return (
    <section className="welcome-section">
      <div className="ai-orb">
        <div className="orb-ring ring-one" />
        <div className="orb-ring ring-two" />
        <div className="orb-core">✦</div>
      </div>

      <div className="eyebrow"><span /> YOUR PERSONAL AI SHOPPER <span /></div>

      <h1>What are you<br /><strong>shopping for?</strong></h1>

      <p className="welcome-description">
        Discover products, compare prices, find the best deals and get instant answers with your AI shopping assistant.
      </p>

      <div className="feature-pills">
        <div className="feature-pill">🔎 Smart Search</div>
        <div className="feature-pill">⚡ Instant Answers</div>
        <div className="feature-pill">⭐ Smart Recommendations</div>
      </div>

      <div className="suggestions-grid">
        {suggestions.map((item) => (
          <button className="suggestion-card" key={item.title} onClick={() => onSuggestion(item.text)}>
            <div className="suggestion-icon">{item.icon}</div>
            <div className="suggestion-content">
              <strong>{item.title}</strong>
              <span>{item.text}</span>
            </div>
            <div className="suggestion-arrow">→</div>
          </button>
        ))}
      </div>
    </section>
  );
}

function MessageBubble({ message }) {
  if (message.role === "error") {
    return <div className="message-row error-row"><div className="error-message">⚠ {message.content}</div></div>;
  }

  if (message.role === "user") {
    return (
      <div className="message-row user-row">
        <div className="message-wrapper user-wrapper">
          <div className="message-label">You</div>
          <div className="user-message">{message.content}</div>
        </div>
        <div className="user-avatar">👤</div>
      </div>
    );
  }

  return (
    <div className="message-row assistant-row">
      <div className="assistant-avatar">✦</div>
      <div className="message-wrapper assistant-wrapper">
        <div className="message-label assistant-label">ShopAI <span>●</span></div>
        <div className="assistant-message">
          <FormattedText content={message.content} />
          {message.products?.length > 0 && <ProductGrid products={message.products} />}
        </div>
      </div>
    </div>
  );
}

function FormattedText({ content }) {
  return (
    <div className="formatted-response">
      {String(content).split("\n").map((line, i) => (
        <div className={line.trim() ? "response-line" : "response-space"} key={i}>
          {formatBold(line)}
        </div>
      ))}
    </div>
  );
}

function formatBold(text) {
  return String(text).split(/(\*\*.*?\*\*)/).map((part, i) =>
    part.startsWith("**") && part.endsWith("**")
      ? <strong key={i}>{part.slice(2, -2)}</strong>
      : part
  );
}

function ProductGrid({ products }) {
  return (
    <div className="product-grid">
      {products.map((product, index) => (
        <article className="product-card" key={`${product.product_link}-${index}`}>
          <div className="product-number">{index + 1}</div>
          <div className="product-info">
            <h3>{product.title}</h3>
            <div className="product-meta">
              <span>{product.brand || "Brand unavailable"}</span>
              <span>₹{product.price.toLocaleString("en-IN")}</span>
              <span>{product.discount}% off</span>
              <span>★ {product.avg_rating}</span>
            </div>
            <a
              className="view-product"
              href={product.product_link}
              target="_blank"
              rel="noopener noreferrer"
            >
              View product ↗
            </a>
          </div>
        </article>
      ))}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="message-row assistant-row">
      <div className="assistant-avatar thinking-avatar">✦</div>
      <div className="message-wrapper">
        <div className="message-label assistant-label">ShopAI <span>●</span></div>
        <div className="typing-bubble">
          <div className="typing-dots"><span /><span /><span /></div>
          <div className="thinking-text">Finding the best answer...</div>
        </div>
      </div>
    </div>
  );
}

export default App;
