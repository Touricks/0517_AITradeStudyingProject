import { Fragment } from "react";
import { Icon } from "./Icon.jsx";

export function Breadcrumb({ items, onNav }) {
  return (
    <div className="breadcrumb">
      {items.map((it, i) => (
        <Fragment key={i}>
          {i > 0 && <span className="sep"><Icon.ChevronR size={12}/></span>}
          {it.to ? (
            <a href="#" onClick={(e) => { e.preventDefault(); onNav(it.to); }}>{it.label}</a>
          ) : (
            <span>{it.label}</span>
          )}
        </Fragment>
      ))}
    </div>
  );
}
