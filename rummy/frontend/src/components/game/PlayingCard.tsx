import type { DragEvent } from "react";

interface Props {
  code: string;
  selected?: boolean;
  onClick?: () => void;
  small?: boolean;
  wild?: boolean;
  faceDown?: boolean;
  draggable?: boolean;
  onDragStart?: (e: DragEvent) => void;
  onDragEnd?: () => void;
  className?: string;
}

const SUIT = {
  S: { glyph: "♠", red: false },
  H: { glyph: "♥", red: true },
  D: { glyph: "♦", red: true },
  C: { glyph: "♣", red: false },
} as const;

function parse(code: string) {
  if (code.startsWith("PJ")) return { rank: "", glyph: "", red: false, joker: true };
  // strip trailing deck index digit(s)
  const body = code.replace(/\d+$/, "");
  const suitChar = body.slice(-1) as keyof typeof SUIT;
  const rank = body.slice(0, -1);
  const s = SUIT[suitChar] ?? { glyph: "?", red: false };
  return { rank, glyph: s.glyph, red: s.red, joker: false };
}

export default function PlayingCard({
  code, selected, onClick, small, wild, faceDown, draggable, onDragStart, onDragEnd, className,
}: Props) {
  const size = [small ? "w-12 h-[4.5rem]" : "w-20 h-28", className].filter(Boolean).join(" ");

  if (faceDown) {
    return (
      <div
        className={[
          size,
          "rounded-lg border-2 border-gold-500/50 shadow-card bg-felt-800",
          "bg-[repeating-linear-gradient(135deg,rgba(212,175,55,0.15)_0px,rgba(212,175,55,0.15)_3px,transparent_3px,transparent_9px)]",
          "flex items-center justify-center",
        ].join(" ")}
      >
        <div className="w-2.5 h-2.5 rounded-full bg-gold-500/70" />
      </div>
    );
  }

  const c = parse(code);
  const pipSize = small ? "text-[10px]" : "text-sm";
  const glyphSize = small ? "text-xl" : "text-3xl";

  return (
    <button
      type="button"
      onClick={onClick}
      draggable={draggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={[
        size,
        "relative rounded-lg shadow-lg select-none border",
        "transition-transform hover:-translate-y-1.5 hover:shadow-xl",
        draggable ? "cursor-grab active:cursor-grabbing" : "",
        wild
          ? "bg-gradient-to-br from-gold-300 to-gold-500 border-gold-600"
          : "bg-gradient-to-b from-white to-slate-50 border-slate-300",
        selected ? "-translate-y-3 ring-2 ring-gold-500 shadow-glow" : "",
      ].join(" ")}
    >
      {c.joker ? (
        <div className="w-full h-full flex flex-col items-center justify-center gap-0.5 bg-gradient-to-br from-purple-500 to-purple-800 rounded-lg text-white">
          <span className={small ? "text-base" : "text-xl"}>🃏</span>
          <span className="text-[8px] font-bold tracking-wider">JOKER</span>
        </div>
      ) : (
        <>
          <div className={`absolute top-0.5 left-1 flex flex-col items-center leading-none font-display font-bold ${pipSize} ${c.red ? "text-red-600" : "text-ink-950"}`}>
            <span>{c.rank}</span>
            <span>{c.glyph}</span>
          </div>
          <div className={`w-full h-full flex items-center justify-center ${glyphSize} ${c.red ? "text-red-600" : "text-ink-950"}`}>
            {c.glyph}
          </div>
          <div className={`absolute bottom-0.5 right-1 flex flex-col items-center leading-none font-display font-bold rotate-180 ${pipSize} ${c.red ? "text-red-600" : "text-ink-950"}`}>
            <span>{c.rank}</span>
            <span>{c.glyph}</span>
          </div>
          {wild && (
            <span className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-gold-500 border border-gold-700 text-[9px] flex items-center justify-center">
              ★
            </span>
          )}
        </>
      )}
    </button>
  );
}
