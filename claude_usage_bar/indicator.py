"""AppIndicator (bandeja) + menu + timer. Camada GTK; orquestra contas/model/icon."""
from __future__ import annotations

import os
import tempfile
import threading
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import Gtk, GLib, AyatanaAppIndicator3 as AppIndicator  # noqa: E402

from . import icon  # noqa: E402
from .accounts import discover  # noqa: E402
from .format import bar_unicode, reset_text, level, format_bar  # noqa: E402
from .model import MultiModel  # noqa: E402

APP_ID = "claude-usage-bar"
REFRESH_S = 300
LABEL_GUIDE = "P 99/99  E 99/99  S 99/99"  # reserva de largura p/ ~3 contas


class TrayApp:
    def __init__(self) -> None:
        self.model = MultiModel(accounts=discover())
        self._icon_dir = tempfile.mkdtemp(prefix="claude-usage-bar-")
        self._icon_counter = 0

        self.indicator = AppIndicator.Indicator.new(
            APP_ID, "", AppIndicator.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_icon_theme_path(self._icon_dir)
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self._set_icon(None, "idle")
        self.indicator.set_label("…", LABEL_GUIDE)
        self.indicator.set_menu(self._build_menu())

        self.refresh()
        GLib.timeout_add_seconds(REFRESH_S, self._on_timer)

    # ---- ícone ----
    def _set_icon(self, pct, state) -> None:
        self._icon_counter += 1
        name = f"gauge-{self._icon_counter}"
        path = os.path.join(self._icon_dir, name + ".png")
        icon.render_png(path, pct, state)
        self.indicator.set_icon_full(name, "Claude usage")

    def _worst(self):
        """Pior caso (maior %) entre todas as contas com dados; None se nenhuma."""
        pcts = [
            max(r.usage.five_hour_pct, r.usage.seven_day_pct)
            for r in self.model.results if r.usage
        ]
        return max(pcts) if pcts else None

    def _update_icon(self) -> None:
        worst = self._worst()
        if worst is None:
            self._set_icon(None, "idle")
        else:
            self._set_icon(worst, level(worst))

    def _label_text(self) -> str:
        """Texto fixo na barra: 'P 4/4  E 48/11  S 12/20'."""
        if not self.model.accounts:
            return "sem contas"
        if not self.model.results:
            return "…"
        items = [
            (
                r.account.label,
                r.usage.five_hour_pct if r.usage else None,
                r.usage.seven_day_pct if r.usage else None,
            )
            for r in self.model.results
        ]
        return format_bar(items)

    # ---- menu ----
    def _build_menu(self) -> Gtk.Menu:
        menu = Gtk.Menu()

        header = Gtk.MenuItem(label="Uso do plano")
        header.set_sensitive(False)
        menu.append(header)

        if not self.model.accounts:
            none_item = Gtk.MenuItem(label="  nenhuma conta Claude encontrada")
            none_item.set_sensitive(False)
            menu.append(none_item)

        for r in self.model.results:
            menu.append(Gtk.SeparatorMenuItem())
            section = Gtk.MenuItem(label=r.account.label.upper())
            section.set_sensitive(False)
            menu.append(section)

            if r.usage:
                rows = [
                    ("5h", r.usage.five_hour_pct, r.usage.five_hour_reset_epoch),
                    ("7d", r.usage.seven_day_pct, r.usage.seven_day_reset_epoch),
                ]
                for lbl, pct, epoch in rows:
                    txt = f"  {lbl}  ▕{bar_unicode(pct)}▏  {pct:.0f}%   {reset_text(epoch)}"
                    item = Gtk.MenuItem(label=txt.rstrip())
                    item.set_sensitive(False)
                    menu.append(item)
            else:
                err = Gtk.MenuItem(label=f"  ⚠ {r.error or 'sem dados'}")
                err.set_sensitive(False)
                menu.append(err)

        if self.model.accounts and not self.model.results:
            loading = Gtk.MenuItem(label="  carregando…")
            loading.set_sensitive(False)
            menu.append(loading)

        menu.append(Gtk.SeparatorMenuItem())

        upd = self.model.last_updated
        when = time.strftime("%H:%M:%S", time.localtime(upd)) if upd else ""
        refresh_item = Gtk.MenuItem(label=f"↻ Atualizar agora        {when}".rstrip())
        refresh_item.connect("activate", lambda _w: self.refresh())
        menu.append(refresh_item)

        quit_item = Gtk.MenuItem(label="⏻ Sair")
        quit_item.connect("activate", lambda _w: Gtk.main_quit())
        menu.append(quit_item)

        menu.show_all()
        return menu

    def _rebuild_menu(self) -> None:
        self.indicator.set_menu(self._build_menu())

    # ---- refresh ----
    def _on_timer(self) -> bool:
        self.refresh()
        return True  # mantém o timer recorrente

    def refresh(self) -> None:
        self.model.is_loading = True
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self) -> None:
        self.model.run_refresh()
        GLib.idle_add(self._apply)

    def _apply(self) -> bool:
        self.model.is_loading = False
        self._update_icon()
        self.indicator.set_label(self._label_text(), LABEL_GUIDE)
        self._rebuild_menu()
        return False  # idle_add one-shot


def main() -> None:
    TrayApp()
    Gtk.main()
