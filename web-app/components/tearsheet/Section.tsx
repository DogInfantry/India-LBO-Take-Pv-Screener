export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-edge bg-panel p-4">
      <h2 className="mb-3 font-mono text-[11px] uppercase tracking-wider text-faint">{title}</h2>
      {children}
    </section>
  );
}
