export function Footer() {
  return (
    <footer
      className="flex items-center justify-center px-5 border-t"
      style={{
        height: 36,
        background: "var(--color-bg-elevated)",
        borderColor: "var(--color-border-secondary)",
      }}
    >
      <div className="flex items-center gap-2">
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: "var(--color-text-accent)",
            fontFamily: "var(--font-display)",
            letterSpacing: "0.05em",
          }}
        >
          MYRAA
        </span>
        <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>—</span>
        <span style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>
          Your Personal AI Assistant
        </span>
        <span style={{ fontSize: 11, color: "var(--color-status-error)" }}>❤</span>
        <span style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>
          Always with you.
        </span>
      </div>
    </footer>
  );
}
