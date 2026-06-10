"""AppIndicator (bandeja) + menu vivo + timer. Camada GTK; orquestra contas/model/icon."""
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
from . import notifications  # noqa: E402
from .accounts import discover  # noqa: E402
from .format import bar_unicode, reset_text, level, format_bar  # noqa: E402
from .model import MultiModel  # noqa: E402

APP_ID = "claude-usage-bar"
REFRESH_S = 300
LABEL_GUIDE = "P 99/99  E 99/99  S 99/99"  # reserva de largura p/ ~3 contas


class TrayApp:
    def __init__(self) -> None:
        self.model = MultiModel(accounts=discover())
        self._prev_results = []
        self._icon_dir = tempfile.mkdtemp(prefix="claude-usage-bar-")
        self._icon_counter = 0
        self._rows = {}            # label -> {"r5": MenuItem, "r7": MenuItem}
        self._updated_item = None

        self.indicator = AppIndicator.Indicator.new(
            APP_ID, "", AppIndicator.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_icon_theme_path(self._icon_dir)
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self._set_icon(None, "idle")
        self.indicator.set_label("…", LABEL_GUIDE)

        self.indicator.set_menu(self._build_menu_once())

        self.refresh()
        GLib.timeout_add_seconds(REFRESH_S, self._on_timer)
        GLib.timeout_add_seconds(1, self._tick)  # countdown vivo enquanto o menu está aberto

    # ---- ícone ----
    def _set_icon(self, pct, state) -> None:
        self._icon_counter += 1
        name = f"gauge-{self._icon_counter}"
        path = os.path.join(self._icon_dir, name + ".png")
        icon.render_png(path, pct, state)
        self.indicator.set_icon_full(name, "Claude usage")

    def _worst(self):
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

    # ---- menu (construído UMA vez; atualizado in-place p/ não fechar) ----
    @staticmethod
    def _disabled(label):
        item = Gtk.MenuItem(label=label)
        item.set_sensitive(False)
        return item

    @staticmethod
    def _set(item, text):
        if item.get_label() != text:
            item.set_label(text)

    def _build_menu_once(self) -> Gtk.Menu:
        menu = Gtk.Menu()
        menu.append(self._disabled("Uso do plano"))

        if not self.model.accounts:
            menu.append(self._disabled("  nenhuma conta Claude encontrada"))

        for a in self.model.accounts:
            menu.append(Gtk.SeparatorMenuItem())
            menu.append(self._disabled(a.label.upper()))
            r5 = self._disabled("  5h  …")
            r7 = self._disabled("  7d  …")
            menu.append(r5)
            menu.append(r7)
            self._rows[a.label] = {"r5": r5, "r7": r7}

        menu.append(Gtk.SeparatorMenuItem())
        self._updated_item = self._disabled("atualizado --:--:--")
        menu.append(self._updated_item)

        quit_item = Gtk.MenuItem(label="⏻ Sair")
        quit_item.connect("activate", lambda _w: Gtk.main_quit())
        menu.append(quit_item)

        menu.connect("show", self._on_show)  # refresh ao abrir (se o host emitir)
        menu.show_all()
        self._menu = menu
        return menu

    def _row_text(self, lbl, pct, epoch) -> str:
        return f"  {lbl}  ▕{bar_unicode(pct)}▏  {pct:.0f}%   {reset_text(epoch)}".rstrip()

    def _render(self) -> None:
        by = {r.account.label: r for r in self.model.results}
        for label, row in self._rows.items():
            r = by.get(label)
            if r is None:
                continue
            if r.usage:
                self._set(row["r5"], self._row_text("5h", r.usage.five_hour_pct, r.usage.five_hour_reset_epoch))
                self._set(row["r7"], self._row_text("7d", r.usage.seven_day_pct, r.usage.seven_day_reset_epoch))
            else:
                self._set(row["r5"], f"  ⚠ {r.error or 'sem dados'}")
                self._set(row["r7"], "")
        if self.model.last_updated:
            self._set(self._updated_item, time.strftime("atualizado %H:%M:%S", time.localtime(self.model.last_updated)))

    # ---- refresh / ticks ----
    def _on_show(self, _w) -> None:
        upd = self.model.last_updated
        if upd is None or (time.time() - upd) > 10:
            self.refresh()

    def _on_timer(self) -> bool:
        self.refresh()
        return True

    def _tick(self) -> bool:
        # recomputa só os textos (countdown anda); _set evita tráfego à toa
        self._render()
        return True

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
        self._render()
        for msg in notifications.notifications_to_fire(self._prev_results, self.model.results):
            notifications.send("Claude — limite de uso", msg)
        self._prev_results = self.model.results
        return False


def main() -> None:
    TrayApp()
    Gtk.main()
