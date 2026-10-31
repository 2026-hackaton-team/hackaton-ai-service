import { Icon } from './ui.jsx';
import './feature-preview.css';

// 화면 상단 탭(인맥 관리 · 받은 일정에서 함께 사용)
export function SectionTabs({ tabs, value, onChange, prefix, label }) {
  function move(event, index) {
    const offsets = { ArrowRight: 1, ArrowLeft: -1 };
    let next;
    if (event.key in offsets) next = (index + offsets[event.key] + tabs.length) % tabs.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = tabs.length - 1;
    else return;
    event.preventDefault();
    onChange(tabs[next].id);
    document.getElementById(`${prefix}-${tabs[next].id}-tab`)?.focus();
  }
  return <div className="feature-tabs" role="tablist" aria-label={label}>
    {tabs.map((item, index) => <button type="button" role="tab" key={item.id}
      id={`${prefix}-${item.id}-tab`} aria-controls={`${prefix}-${item.id}-panel`}
      aria-selected={value === item.id} tabIndex={value === item.id ? 0 : -1}
      onKeyDown={event => move(event, index)} onClick={() => onChange(item.id)}>
      <Icon name={item.icon} size={17} />{item.label}
    </button>)}
  </div>;
}
