export default function YearTag({ text, subtitle }: { text: string; subtitle: string }) {
  return (
    <div className="year-tag">
      <span className="year-slash">/</span>
      {text}
      <div className="year-sub">{subtitle}</div>
    </div>
  );
}
