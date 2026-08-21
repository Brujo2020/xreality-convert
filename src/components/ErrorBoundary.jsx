import React from 'react';
import { WarningOctagon, ArrowClockwise } from '@phosphor-icons/react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Unhandled UI Exception caught by ErrorBoundary:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="grid h-screen w-screen place-items-center bg-[#020b1a] p-6 text-slate-100 font-sans select-none">
          <div className="notice-card notice-error max-w-lg rounded-3xl border border-rose-500/20 bg-rose-950/20 p-8 text-center backdrop-blur-2xl shadow-2xl">
            <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-rose-400/30 bg-rose-500/10 text-rose-300 shadow-[0_0_30px_rgba(244,63,94,0.2)]">
              <WarningOctagon size={32} weight="duotone" aria-hidden="true" />
            </div>
            
            <p className="mt-4 font-mono text-[9px] uppercase tracking-[0.2em] text-rose-300/70">
              Escudo de Estabilidad UI
            </p>
            <h1 className="mt-1 text-xl font-bold tracking-tight text-white">
              Se ha prevenido una falla de pantalla
            </h1>
            <p className="mt-2 text-xs leading-relaxed text-slate-300">
              {this.state.error?.message || 'Ocurrió un error inesperado al renderizar la interfaz.'}
            </p>

            {this.state.errorInfo?.componentStack && (
              <details className="mt-4 text-left">
                <summary className="cursor-pointer font-mono text-[9px] uppercase tracking-wider text-rose-300/60 hover:text-rose-200">
                  Detalles del error (Stack)
                </summary>
                <pre className="scroll-dark mt-2 max-h-36 overflow-auto rounded-xl border border-white/5 bg-black/50 p-3 font-mono text-[10px] leading-relaxed text-rose-200/80">
                  <code>{this.state.error?.stack || this.state.errorInfo.componentStack}</code>
                </pre>
              </details>
            )}

            <div className="mt-6 flex justify-center gap-3">
              <button
                type="button"
                onClick={this.handleReset}
                className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-rose-600 to-pink-600 px-5 py-2.5 text-xs font-semibold text-white shadow-lg shadow-rose-950/40 transition hover:brightness-110"
              >
                <ArrowClockwise size={16} weight="bold" />
                Recargar Aplicación
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
