import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { Send, Bot, User, MessageCircle, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import logoUrl from "./assets/favicon.png";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome-msg",
      role: "assistant",
      content: import.meta.env.VITE_CHAT_GREETING || "Hello. I'm your assistant. How can I help you today?",
    }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const sendMessage = async () => {
    const question = input.trim();
    if (!question) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const res = await axios.post("http://localhost:8080/autoupdate-agent/query", {
        question,
      });

      const botMessage: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: res.data.answer,
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (err) {
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "An error occurred with the agent server.",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div style={{ position: "fixed", bottom: "24px", right: "24px", zIndex: 9999, fontFamily: "sans-serif" }}>
      
      {/* Launcher Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          style={{
            width: 60,
            height: 60,
            borderRadius: "50%",
            background: "#14ff72",
            color: "black",
            border: "none",
            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "transform 0.2s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.transform = "scale(1.05)")}
          onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}
        >
          <MessageCircle size={28} />
        </button>
      )}

      {/* Chat Window */}
      {isOpen && (
        <div style={{ 
          width: "380px", 
          height: "600px", 
          maxHeight: "80vh",
          display: "flex", 
          flexDirection: "column",
          background: "white",
          borderRadius: "24px",
          boxShadow: "0 10px 40px rgba(0,0,0,0.15)",
          overflow: "hidden"
        }}>
          
          {/* Header */}
          <header style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "20px 24px",
            background: "#14ff72",
            borderBottom: "1px solid rgba(0,0,0,0.1)",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <img src={logoUrl} alt="Logo" style={{ height: 32, width: 32, objectFit: "contain" }} />
              <div>
                <h1 style={{ fontSize: 16, fontWeight: "bold", color: "#000000", margin: 0, letterSpacing: "-0.01em" }}>{import.meta.env.VITE_CHAT_NAME || "regolino"}</h1>
                <p style={{ fontSize: 12, color: "#000000", margin: 0 }}>{import.meta.env.VITE_CHAT_SUBTITLE || "powered by regolo.ai"}</p>
              </div>
            </div>
            <button 
              onClick={() => setIsOpen(false)}
              style={{
                background: "transparent",
                border: "none",
                color: "#000000",
                cursor: "pointer",
                padding: 4,
                display: "flex"
              }}
            >
              <X size={20} />
            </button>
          </header>

          {/* Chat Area */}
          <div
            style={{
              flex: 1,
              background: "var(--panel-bg)",
              overflowY: "auto",
              padding: "24px 20px",
              display: "flex",
              flexDirection: "column",
              gap: 20,
            }}
          >
        {messages.map((m) => {
          const isUser = m.role === "user";
          return (
            <div
              key={m.id}
              className="animate-fade-in"
              style={{
                display: "flex",
                flexDirection: isUser ? "row-reverse" : "row",
                alignItems: "flex-end",
                gap: 12,
              }}
            >
              {/* Avatar */}
              <div style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: isUser ? "#e4e4e7" : "#18181b",
                color: isUser ? "#52525b" : "#ffffff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0
              }}>
                {isUser ? <User size={16} /> : <Bot size={16} />}
              </div>

              {/* Message Bubble */}
              <div
                style={{
                  maxWidth: "75%",
                  padding: "14px 18px",
                  borderRadius: 20,
                  borderBottomRightRadius: isUser ? 4 : 20,
                  borderBottomLeftRadius: !isUser ? 4 : 20,
                  background: isUser ? "var(--user-msg-bg)" : "var(--bot-msg-bg)",
                  color: isUser ? "var(--user-msg-text)" : "var(--bot-msg-text)",
                  lineHeight: 1.5,
                  fontSize: 15,
                  overflowWrap: "break-word",
                }}
              >
                {isUser ? (
                  <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
                ) : (
                  <div className="markdown-body">
                    <ReactMarkdown>{m.content}</ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Typing Indicator */}
        {loading && (
          <div className="animate-fade-in" style={{ display: "flex", alignItems: "flex-end", gap: 12 }}>
            <div style={{ width: 32, height: 32, borderRadius: "50%", background: "#18181b", color: "#ffffff", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <Bot size={16} />
            </div>
            <div style={{ background: "var(--bot-msg-bg)", padding: "14px 18px", borderRadius: 20, borderBottomLeftRadius: 4 }}>
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div style={{
        background: "var(--panel-bg)",
        padding: "20px 24px",
        borderTop: "1px solid var(--border-color)",
        borderBottomLeftRadius: 24,
        borderBottomRightRadius: 24,
      }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          background: "#f4f4f5",
          border: "1px solid transparent",
          borderRadius: 32,
          padding: "6px 6px 6px 20px",
          transition: "all 0.2s ease",
        }}
        onFocus={(e) => e.currentTarget.style.border = "1px solid #d4d4d8"}
        onBlur={(e) => e.currentTarget.style.border = "1px solid transparent"}
        >
          <input
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              fontSize: 15,
              color: "var(--text-primary)",
              padding: "10px 0",
            }}
            value={input}
            placeholder={import.meta.env.VITE_CHAT_PLACEHOLDER || "Ask a question..."}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            style={{
              background: input.trim() ? "#14ff72" : "#e4e4e7",
              color: input.trim() ? "#000000" : "#a1a1aa",
              border: "none",
              borderRadius: "50%",
              width: 40,
              height: 40,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: input.trim() ? "pointer" : "not-allowed",
              transition: "all 0.2s ease",
              flexShrink: 0,
            }}
          >
            <Send size={18} style={{ marginLeft: -2, marginTop: 2 }} />
          </button>
        </div>
      </div>
      </div>
      )}
    </div>
  );
}

export default App;