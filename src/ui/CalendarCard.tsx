interface CalendarCardProps {
  date: Date;
}

const DAYS = ["S", "M", "T", "W", "T", "F", "S"];
const MONTHS = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
  "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"];

export function CalendarCard({ date }: CalendarCardProps) {
  const year = date.getFullYear();
  const month = date.getMonth();
  const today = date.getDate();
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const weeks: (number | null)[][] = [];
  let currentWeek: (number | null)[] = new Array(firstDay).fill(null);

  for (let d = 1; d <= daysInMonth; d++) {
    currentWeek.push(d);
    if (currentWeek.length === 7) {
      weeks.push(currentWeek);
      currentWeek = [];
    }
  }
  if (currentWeek.length > 0) {
    while (currentWeek.length < 7) currentWeek.push(null);
    weeks.push(currentWeek);
  }

  const dayNames = DAYS;
  // Map 0=Sun, 1=Mon... to the reference layout S M T W T F S
  const dayLabels = ["S", "M", "T", "W", "T", "F", "S"];

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        flex: 1,
        minWidth: 260,
        background: "rgba(8, 12, 24, 0.85)",
        border: "1px solid rgba(0, 212, 255, 0.1)",
      }}
    >
      <div
        className="px-4 py-3 border-b"
        style={{ borderColor: "rgba(0, 212, 255, 0.08)" }}
      >
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "0.12em",
            color: "#e0e8ff",
            fontFamily: '"Space Grotesk", sans-serif',
          }}
        >
          CALENDAR
        </span>
      </div>

      <div className="p-4">
        <div className="flex items-start gap-6">
          {/* Calendar grid */}
          <div>
            {/* Day headers */}
            <div className="grid grid-cols-7 gap-1 mb-1">
              {dayLabels.map((d, i) => (
                <div
                  key={i}
                  className="text-center"
                  style={{
                    width: 24,
                    fontSize: 9,
                    fontWeight: 600,
                    color: "#4a5568",
                    letterSpacing: "0.05em",
                  }}
                >
                  {d}
                </div>
              ))}
            </div>

            {/* Weeks */}
            {weeks.map((week, wi) => (
              <div key={wi} className="grid grid-cols-7 gap-1">
                {week.map((day, di) => (
                  <div
                    key={di}
                    className="text-center flex items-center justify-center"
                    style={{
                      width: 24,
                      height: 24,
                      fontSize: 10,
                      fontWeight: day === today ? 700 : 400,
                      color: day === today ? "#ffffff" : day ? "#7a8599" : "transparent",
                      background: day === today ? "rgba(0, 212, 255, 0.3)" : "transparent",
                      borderRadius: day === today ? "50%" : 0,
                      border: day === today ? "1px solid rgba(0, 212, 255, 0.5)" : "none",
                    }}
                  >
                    {day}
                  </div>
                ))}
              </div>
            ))}
          </div>

          {/* Right side info */}
          <div className="flex flex-col gap-2">
            <div>
              <div style={{ fontSize: 10, color: "#4a5568", letterSpacing: "0.1em", fontWeight: 600 }}>
                {dayNames[date.getDay()]?.toUpperCase()}
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#e0e8ff", fontFamily: '"Space Grotesk", sans-serif' }}>
                {today} {MONTHS[month]} {year}
              </div>
            </div>

            <div
              style={{
                fontSize: 11,
                color: "#7a8599",
                paddingTop: 8,
                borderTop: "1px solid rgba(0, 212, 255, 0.06)",
              }}
            >
              No events today
            </div>

            <button
              className="mt-2 px-3 py-1.5 rounded-lg text-center transition-colors"
              style={{
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.05em",
                color: "#00d4ff",
                background: "rgba(0, 212, 255, 0.08)",
                border: "1px solid rgba(0, 212, 255, 0.15)",
              }}
            >
              View Full Calendar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
