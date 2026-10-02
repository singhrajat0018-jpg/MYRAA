import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Search,
  Mic,
  Send,
  ChevronDown,
  X as CloseIcon,
  Image,
  Video,
  Code,
  MessageCircle,
  Paperclip
} from "lucide-react";

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  themeColor: string;
  onSendMessage: (message: string) => void;
  onToggleMic: () => void;
  isListening: boolean;
  messages: Array<{
    id: string;
    text: string;
    isUser: boolean;
    timestamp: string;
    type?: "text" | "image" | "video" | "code";
    url?: string;
  }>;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  isOpen,
  onClose,
  themeColor,
  onSendMessage,
  onToggleMic,
  isListening,
  messages
}) => {
  const [inputValue, setInputValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isAttachedMenuOpen, setIsAttachedMenuOpen] = useState(false);

  const getThemeColors = () => {
    switch (themeColor) {
      case "violet":
        return { accent: "text-purple-400 glow-purple", bg: "bg-purple-900/50" };
      case "crimson":
        return { accent: "text-rose-400 glow-rose", bg: "bg-rose-900/50" };
      case "emerald":
        return { accent: "text-emerald-400 glow-emerald", bg: "bg-emerald-900/50" };
      case "celestial":
        return { accent: "text-sky-400 glow-sky", bg: "bg-sky-900/50" };
      case "gold":
        return { accent: "text-cyan-400 glow-cyan", bg: "bg-cyan-900/50" };
      case "rose":
        return { accent: "text-pink-400 glow-pink", bg: "bg-pink-900/50" };
      case "charcoal":
      default:
        return { accent: "text-cyan-400 glow-cyan", bg: "bg-cyan-900/50" };
    }
  };

  const { accent, bg } = getThemeColors();

  const handleSend = () => {
    if (inputValue.trim()) {
      onSendMessage(inputValue.trim());
      setInputValue("");
      textareaRef.current?.blur();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleAttachClick = () => {
    setIsAttachedMenuOpen(!isAttachedMenuOpen);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 z-30 backdrop-blur-sm"
          />

          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 20, stiffness: 170 }}
            className="fixed right-0 top-0 bottom-0 w-80 bg-[#020206]/95 backdrop-blur-xl border-l border-white/10 z-40 flex flex-col"
          >
            <div className="flex items-center justify-between p-4 border-b border-white/5">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-xl border ${accent}`}>
                  <MessageCircle size={20} className="animate-pulse" />
                </div>
                <h3 className="font-display font-medium text-lg tracking-tight text-white">
                  CHAT
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={onClose}
                  className="p-1 rounded hover:bg-white/5 transition"
                >
                  <CloseIcon size={18} />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.map((msg) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                  className={`flex ${msg.isUser ? "justify-end" : "justify-start"} space-x-3 max-w-[80%] `}
                >
                  {!msg.isUser && (
                    <div className={`p-2 rounded-full ${accent}`}>
                      <MessageCircle size={16} />
                    </div>
                  )}
                  <div className={`flex flex-col max-w-full ${msg.isUser ? bg : "bg-black/40"} rounded-lg p-3 `}>
                    {msg.type === "image" && (
                      <img
                        src={msg.url || ""}
                        alt="Generated image"
                        className="max-w-full h-auto rounded mb-2"
                      />
                    )}
                    {msg.type === "video" && (
                      <video
                        src={msg.url || ""}
                        controls
                        className="max-w-full h-auto rounded mb-2"
                      />
                    )}
                    {msg.type === "code" && (
                      <pre className="bg-black/60 text-xs p-2 rounded overflow-auto">
                        <code className="text-cyan-200">{msg.text}</code>
                      </pre>
                    )}
                    {!msg.type || msg.type === "text" && (
                      <p className={`text-xs ${msg.isUser ? "text-slate-200" : "text-white"} leading-relaxed break-words`}>
                        {msg.text}
                      </p>
                    )}
                    <span className={`block text-[9px] ${msg.isUser ? "text-slate-500" : "text-slate-400"} mt-1`}>{msg.timestamp}</span>
                  </div>
                  {msg.isUser && (
                    <div className={`p-2 rounded-full ${accent}`}>
                      <MessageCircle size={16} />
                    </div>
                  )}
                </motion.div>
              ))}
              <div className="flex h-[80px] items-center justify-center">
                <span className="text-xs text-slate-400">No messages yet</span>
              </div>
            </div>

            <div className="flex items-center p-4 border-t border-white/5">
              <button
                onClick={handleAttachClick}
                className="p-2 rounded hover:bg-white/5 transition"
              >
                <Paperclip size={20} />
              </button>

              <textarea
                ref={textareaRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Talk to MYRAA..."
                className={`flex-1 min-h-[44px] resize-none bg-black/40 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/60 px-3 py-2 rounded-lg text-sm`}
              />

              <div className="flex items-center gap-2">
                <button
                  onClick={onToggleMic}
                  className={`p-2 rounded ${isListening ? "bg-cyan-500/30 hover:bg-cyan-500/40" : "hover:bg-white/5"} transition`}
                >
                  {isListening ? <Mic size={20} className="text-cyan-400 animate-pulse" /> : <Mic size={20} />}
                </button>
                <button
                  onClick={handleSend}
                  className="p-2 rounded hover:bg-white/5 transition"
                >
                  <Send size={20} />
                </button>
              </div>
            </div>

            {isAttachedMenuOpen && (
              <motion.div
                initial={{ opacity: 0, y: -10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -10, scale: 0.95 }}
                className="absolute bottom-16 right-6 w-48 bg-black/90 backdrop-blur-xl rounded-lg border border-white/10 z-50"
              >
                <div className="space-y-2 p-3">
                  <button
                    onClick={() => {/* Handle image attachment */}}
                    className="flex items-center gap-2 w-full text-left text-sm p-2 rounded hover:bg-white/5 transition"
                  >
                    <Image size={16} />
                    <span>Image</span>
                  </button>
                  <button
                    onClick={() => {/* Handle video attachment */}}
                    className="flex items-center gap-2 w-full text-left text-sm p-2 rounded hover:bg-white/5 transition"
                  >
                    <Video size={16} />
                    <span>Video</span>
                  </button>
                  <button
                    onClick={() => {/* Handle file attachment */}}
                    className="flex items-center gap-2 w-full text-left text-sm p-2 rounded hover:bg-white/5 transition"
                  >
                    <Paperclip size={16} />
                    <span>File</span>
                  </button>
                  <button
                    onClick={() => {/* Handle code snippet */}}
                    className="flex items-center gap-2 w-full text-left text-sm p-2 rounded hover:bg-white/5 transition"
                  >
                    <Code size={16} />
                    <span>Code</span>
                  </button>
                </div>
              </motion.div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};