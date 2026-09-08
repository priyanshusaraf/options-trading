import { useEffect, useRef, useState, type ReactNode } from 'react'
import { ArrowUpRight, FilePlus2, LayoutTemplate, X } from 'lucide-react'
import type { StrategyApi } from '../../shell/api'
import { CreateDraft } from './CreateDraft'

export function StrategyDialog({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const previous = useRef(document.activeElement as HTMLElement | null)
  useEffect(() => {
    const element = dialog.current
    element?.showModal()
    return () => { element?.close(); if (previous.current?.isConnected) previous.current.focus() }
  }, [])
  return <dialog ref={dialog} className="slate-strategy-dialog" aria-labelledby="strategy-dialog-title"
    onCancel={(event) => { event.preventDefault(); onClose() }}>
    <header><h2 id="strategy-dialog-title">{title}</h2><button type="button" aria-label="Close new strategy" onClick={onClose}><X size={19} aria-hidden="true" /></button></header>
    {children}
  </dialog>
}

export function NewStrategy({ api, projectId, onCreated, onPresets }: {
  api: StrategyApi; projectId?: string; onCreated: (projectId: string, identifier: string) => void; onPresets: () => void
}) {
  const [step, setStep] = useState<'choice' | 'fresh' | null>(null)
  const close = () => setStep(null)
  return <><button className="slate-primary-action" onClick={() => setStep('choice')}><FilePlus2 size={17} aria-hidden="true" />New strategy</button>
    {step && <StrategyDialog title={step === 'choice' ? 'How would you like to start?' : 'Start fresh'} onClose={close}>
      {step === 'choice' ? <div className="slate-start-options">
        <button autoFocus onClick={() => setStep('fresh')}><FilePlus2 size={24} aria-hidden="true" /><strong>Start fresh</strong><span>Build your own strategy from an empty draft.</span><ArrowUpRight size={18} aria-hidden="true" /></button>
        <button onClick={() => { close(); onPresets() }}><LayoutTemplate size={24} aria-hidden="true" /><strong>Use a preset</strong><span>Explore ready-to-edit rules as your starting point.</span><ArrowUpRight size={18} aria-hidden="true" /></button>
      </div> : <CreateDraft key={projectId} api={api} projectId={projectId} onCreated={(project, identifier) => { close(); onCreated(project, identifier) }} onCancel={close} />}
    </StrategyDialog>}
  </>
}
