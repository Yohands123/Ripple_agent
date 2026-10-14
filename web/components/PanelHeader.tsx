export default function PanelHeader({ sample }: { sample: boolean }) {
  return (
    <div className="panel-header">
      <h1 className="panel-title">Ripple</h1>
      {sample && <div className="sample-tag">SAMPLE DATA</div>}
    </div>
  );
}
