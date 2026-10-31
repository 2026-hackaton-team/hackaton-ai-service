import { useEffect, useId, useState } from 'react';
import { Icon } from './ui.jsx';

export default function PersonSearch({people, value, onChange}) {
  const id = useId();
  const [query,setQuery] = useState('');
  const [open,setOpen] = useState(false);
  const [active,setActive] = useState(0);
  const selected = people.find(person => person.id === value);
  const results = people.filter(person => `${person.name} ${person.relation} ${person.group || ''}`.toLowerCase().includes(query.trim().toLowerCase()));
  const choices = [...results.map(person => ({id:person.id,label:`${person.name} · ${person.relation}${person.group ? ` · ${person.group}` : ''}`})),{id:'__new',label:'+ 새로운 사람 등록'}];
  useEffect(() => { if (open) document.getElementById(`${id}-${Math.min(active,choices.length-1)}`)?.scrollIntoView({block:'nearest'}); }, [open,active,query,choices.length,id]);
  function choose(choice) { onChange(choice.id); setQuery(''); setOpen(false); setActive(0); }
  return <div className="field field-full person-picker" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
    <label className="field-label" htmlFor={id}>누구의 경조사인가요?<span className="field-required" aria-hidden="true">*</span></label>
    <div className="person-search-box"><Icon name="Search" size={16}/><input id={id} className="input" role="combobox" aria-label="경조사 인맥 검색" aria-autocomplete="list" aria-expanded={open} aria-controls={`${id}-results`} aria-activedescendant={open ? `${id}-${Math.min(active,choices.length-1)}` : undefined} placeholder={selected ? `${selected.name} · ${selected.relation}` : value === '__new' ? '새로운 사람 등록 선택됨' : '이름, 관계, 그룹으로 검색'} value={query} onFocus={() => setOpen(true)} onChange={event => {setQuery(event.target.value);onChange('');setOpen(true);setActive(0);}} onKeyDown={event => {
      if (event.key === 'Escape') {event.preventDefault();event.stopPropagation();setOpen(false);}
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {event.preventDefault();setOpen(true);setActive(index => (index + (event.key === 'ArrowDown' ? 1 : choices.length-1)) % choices.length);}
      if (event.key === 'Enter') {event.preventDefault(); if (open) choose(choices[Math.min(active,choices.length-1)]); else setOpen(true);}
    }}/></div>
    {open && <div className="person-search-results"><div className="field-hint" role="status">{results.length ? `검색 결과 ${results.length}명 · 관계와 그룹을 확인해 선택하세요.` : '일치하는 인맥이 없어요. 새로 등록할 수 있습니다.'}</div><ul id={`${id}-results`} role="listbox" aria-label="인맥 검색 결과">{choices.map((choice,index) => <li id={`${id}-${index}`} key={choice.id} role="option" aria-selected={value === choice.id} className={index === active ? 'is-active' : ''} onMouseDown={event => event.preventDefault()} onMouseEnter={() => setActive(index)} onClick={() => choose(choice)}>{choice.label}</li>)}</ul></div>}
    <span className="field-hint">{selected ? `선택한 인맥: ${selected.name} · ${selected.relation}${selected.group ? ` · ${selected.group}` : ''}` : value === '__new' ? '아래에 새 인맥의 이름을 입력해 주세요.' : '검색 결과를 클릭하거나 방향키와 Enter로 선택하세요.'}</span>
  </div>;
}
