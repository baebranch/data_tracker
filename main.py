import os
import sys
import json
import psutil
import ctypes
import asyncio
import logging
import pathlib
import datetime
import winsound
import ctypes.wintypes
import flet as ft
import flet_charts as fch
from desktop_notifier import DesktopNotifier, Icon


logger = logging.getLogger("data_trakr")
OPACITY = 0.2
DEFAULT = 100
DATA_DIR = "data"
VERSION = "1.1.0"
APP_NAME = "Data Tracker"
DATA_FILE = os.path.join(DATA_DIR, "network_data.json")

if getattr(sys, 'frozen', False):
  # Running in a PyInstaller bundle (exe)
  base_path = sys._MEIPASS
else:
  # Running as a script
  base_path = os.path.dirname(__file__)
PATH = pathlib.Path(os.path.join(base_path, "assets", "favicon.ico"))


class Tracker:
  """ Handles the data tracking and storage """
  ready = False # Indicates if Tracker is ready

  def __init__(self):
    # Initialize data tracking variables
    self.start_sent, self.start_recv, self.hourly_data, self.threshold = self.load_data()
    self.last_notified_mb = 0

    # Start notification handler
    self._notifier = DesktopNotifier(
      app_name=APP_NAME,
      app_icon=Icon(path=PATH)
    )

  def get_midnight_timestamp(self):
    """ Return the datetime object for today's midnight """
    now = datetime.datetime.now()
    self.midnight = datetime.datetime.combine(now.date(), datetime.time.min)
    return self.midnight

  def load_data(self):
    """Load accumulated data from JSON."""
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    if os.path.exists(DATA_FILE):
      try:
        with open(DATA_FILE, "r") as f:
          data = json.load(f)
          if data.get("date") == today_str:
            return data.get("sent", 0), data.get("recv", 0), data.get("hourly", [0.0] * 24), data.get("threshold", 50.0)
      except Exception as e:
        logger.error(f"Error loading data: {e}")

    return 0, 0, [0.0] * 24, 50.0

  def save_data(self, sent, recv, last_sent, last_recv, hourly, threshold):
    """Save accumulated data to JSON."""
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    os.makedirs(DATA_DIR, exist_ok=True)

    try:
      with open(DATA_FILE, "w") as f:
        json.dump(
          {
            "date": today_str,
            "sent": sent,
            "recv": recv,
            "last_sent": last_sent,
            "last_recv": last_recv,
            "hourly": hourly,
            "threshold": threshold
          },
          f
        )
    except Exception as e:
      logger.error(f"Error saving data: {e}")
  
  def setup(self, set_sent, set_recv, total, set_total, set_hourly) -> None:
    """ Setup the state variables """
    self.set_sent = set_sent
    self.set_recv = set_recv
    self.total = total
    self.set_total = set_total
    self.set_hourly = set_hourly
    self.ready = True

  def set_threshold(self, threshold: float):
    """Set the notification threshold."""
    self.threshold = threshold
    # Recalculate last_notified_mb based on current total
    if hasattr(self, 'set_total'):
      current_total = self.total
      current_mb = current_total / (1024 * 1024)
      self.last_notified_mb = (current_mb // self.threshold) * self.threshold if self.threshold > 0 else 0

  # async def tracker(accumulated_sent, accumulated_recv, set_sent, set_total, set_recv) -> None:
  async def tracker(self) -> None:
    """ Tracks additional data sent """
    counters = psutil.net_io_counters()
    last_sent = counters.bytes_sent
    last_recv = counters.bytes_recv
    
    total_sent = self.start_sent
    total_recv = self.start_recv
    hourly = list(self.hourly_data)
    
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Initialize last_notified_mb
    initial_total = total_sent + total_recv
    initial_mb = initial_total / (1024 * 1024)
    self.last_notified_mb = (initial_mb // self.threshold) * self.threshold if self.threshold > 0 else 0

    # Continuosly track data usage
    while True:
      # Get current bytes sent and current day
      counters = psutil.net_io_counters()
      now = datetime.datetime.now()
      current_today_str = now.strftime("%Y-%m-%d")
      current_hour = now.hour

      # If day has rolled over, reset all counters
      if current_today_str != today_str:
        # Set new current day string and totals to zero
        today_str = current_today_str
        total_sent = 0
        total_recv = 0
        hourly = [0.0] * 24

      # Calculate deltas, increment totals and reset last
      delta_sent = counters.bytes_sent - last_sent
      delta_recv = counters.bytes_recv - last_recv

      if delta_sent < 0:
        delta_sent = counters.bytes_sent
      if delta_recv < 0:
        delta_recv = counters.bytes_recv

      total_sent += delta_sent
      total_recv += delta_recv

      # Accumulate delta into the current hour bucket
      hourly[current_hour] += delta_sent + delta_recv

      last_sent = counters.bytes_sent
      last_recv = counters.bytes_recv
      
      # Set state variables
      self.set_sent(total_sent)
      self.set_recv(total_recv)
      self.set_total(total_sent + total_recv)
      self.set_hourly(list(hourly))
      
      # Check for notifications
      current_mb = (total_sent + total_recv) / (1024 * 1024)
      if self.threshold > 0 and current_mb >= self.last_notified_mb + self.threshold:
        self.last_notified_mb += self.threshold
        await self._notifier.send("Data Usage Alert", f"Total data used: {current_mb:.2f} MB")
        winsound.MessageBeep()
      
      self.save_data(total_sent, total_recv, last_sent, last_recv, hourly, self.threshold)

      await asyncio.sleep(10)  # update every 10 seconds

def hourly_chart(hourly: list[float]) -> fch.BarChart:
  """ Build a 24-bar chart showing hourly network usage in MB """
  max_y = 100
  current_hour = datetime.datetime.now().hour
  max_mb = max(*[v / (1024 * 1024) for v in hourly], 1)

  groups = [
    fch.BarChartGroup(
      x=i,
      rods=[
        fch.BarChartRod(
          width=7,
          from_y=0,
          border_radius=ft.BorderRadius.all(2),
          to_y=max(((hourly[i] / (1024 * 1024)) / max_mb) * max_y, 1),
          color=ft.Colors.BLUE_400 if i == current_hour else ft.Colors.BLUE_200,
        )
      ]
    )
    for i in range(24)
  ]

  return fch.BarChart(
    max_y=max_y,
    expand=True,
    groups=groups,
    interactive=False
  )


@ft.component
def AppView(page: ft.Page, trak: Tracker) -> list[ft.Control]:
  """ Main application view - manages layout and global state """
  # Create tracker state variables
  sent, set_sent = ft.use_state(trak.start_sent)
  recv, set_recv = ft.use_state(trak.start_recv)
  threshold, set_threshold = ft.use_state(trak.threshold)
  hourly, set_hourly = ft.use_state(list(trak.hourly_data))
  total, set_total = ft.use_state(trak.start_sent + trak.start_recv)

  # Close window on click
  async def close_window(e):
    """ Close window on click """
    await e.page.window.close()

  # Setup the tracker for start
  trak.setup(set_sent, set_recv, total, set_total, set_hourly)

  # Opacity update event handlers
  def mouse_enter(e):
    page.window.opacity = 1
    page.update()
  
  def mouse_exit(e):
    page.window.opacity = OPACITY
    page.update()

  # Threshold change handler
  def on_change(e):
    try:
      if e.control.value == '': return

      new_threshold = float(e.control.value)
      set_threshold(e.control.value)
      trak.set_threshold(new_threshold)
    except ValueError:
      pass  # Ignore invalid input

  hint = "Value (MB)"

  return [
    ft.GestureDetector(
      ft.WindowDragArea(
        ft.Container(
          ft.Column(
            [
              ft.Container(
                ft.Row(
                  [
                    ft.Container(
                      ft.Row(
                        [
                          ft.Text(
                            size=18,
                            expand=True,
                            value=APP_NAME,
                            color=ft.Colors.BLUE,
                            margin=ft.Margin.all(0),
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER
                          )
                        ],
                        expand=True,
                      ),
                      expand=True,
                      margin=ft.Margin.only(left=40),
                      padding=ft.Padding.symmetric(vertical=7, horizontal=0),
                    ),

                    ft.FilledButton(
                      content=ft.Image(
                        width=12,
                        height=12,
                        color=ft.Colors.WHITE,
                        src="./close.svg"
                      ),
                      on_click=close_window,
                      style=ft.ButtonStyle(
                        bgcolor=ft.Colors.SURFACE,
                        padding=ft.Padding.all(14),
                        overlay_color=ft.Colors.RED,
                        shadow_color=ft.Colors.TRANSPARENT,
                        shape=ft.RoundedRectangleBorder(radius=0)
                      ),
                      width=40,
                      height=40,
                      tooltip="Close"
                    ),
                  ],
                  spacing=0,
                  expand=True,
                  margin=ft.Margin.all(0)
                ),
                expand=True,
                border=ft.Border.only(bottom=ft.BorderSide(1,ft.Colors.GREY_800))
              ),
              
              ft.Container(
                ft.Row(
                  [
                    # Sent
                    ft.Text(
                      f"Sent\n {sent / (1024*1024):.2f} MB",
                      text_align=ft.TextAlign.CENTER,
                      expand=True
                    ),

                    # Received with Divider boarder
                    ft.Container(
                      ft.Text(
                        f"Recv\n {recv / (1024*1024):.2f} MB",
                        text_align=ft.TextAlign.CENTER,
                        expand=True
                      ),
                      padding=ft.Padding.symmetric(horizontal=15),
                      border=ft.Border.symmetric(horizontal=ft.BorderSide(1,ft.Colors.GREY_800))
                    ),

                    # Total
                    ft.Text(
                      f"Total\n {total / (1024*1024):.2f} MB",
                      text_align=ft.TextAlign.CENTER,
                      expand=True
                    )
                  ],
                  expand=True,
                  spacing=0
                ),
                padding=ft.Padding.symmetric(vertical=10)
              ),

              # Usage chart
              ft.Container(
                height=100,
                expand=True,
                content=hourly_chart(hourly),
                padding=ft.Padding.symmetric(horizontal=4, vertical=10),
                border=ft.Border.only(top=ft.BorderSide(1,ft.Colors.GREY_800)),
              ),

              # Settings
              ft.Container(
                ft.Row(
                  [
                    ft.Text("Notify every:"),
                    ft.Container(content=
                      ft.TextField(
                        expand=True,
                        hint_text=hint,
                        border_radius=3,
                        multiline=False, 
                        on_change=on_change,
                        value=str(threshold),
                        align=ft.Alignment.CENTER,
                        border=ft.InputBorder.NONE,
                        bgcolor=ft.Colors.TRANSPARENT,
                        border_color=ft.Colors.TRANSPARENT,
                        clip_behavior=ft.ClipBehavior.HARD_EDGE, 
                        content_padding=ft.Padding.only(left=10, top=-22, right=2, bottom=2),
                        hint_style=ft.TextStyle(
                          color=ft.Colors.SECONDARY,
                          weight=ft.FontWeight.NORMAL
                        )
                      ),
                      height=25,
                      expand=True,
                      border_radius=3,
                      bgcolor=ft.Colors.SURFACE,
                      margin=ft.Margin.only(top=5),
                      clip_behavior=ft.ClipBehavior.HARD_EDGE,
                      border=ft.Border.all(1, ft.Colors.PRIMARY),
                      padding=ft.Padding.only(left=0, top=0, right=0, bottom=0)
                    ),
                    ft.Text("MB"),
                  ]
                ),
                padding=ft.Padding.only(left=10, top=5, bottom=10, right=10),
                border=ft.Border.only(top=ft.BorderSide(1,ft.Colors.GREY_800)),
              )
            ],
            spacing=0,
            expand=True
          ),
          expand=True,
          bgcolor=ft.Colors.SURFACE,
        ),
        expand=True
      ),
      on_exit=mouse_exit,
      on_enter=mouse_enter
    )
  ]

async def remove_from_taskbar(title: str) -> None:
  """Use Win32 API to hide the window from the taskbar."""
  GWL_EXSTYLE      = -20
  WS_EX_APPWINDOW  = 0x00040000
  WS_EX_TOOLWINDOW = 0x00000080
  SWP_NOMOVE       = 0x0002
  SWP_NOSIZE       = 0x0001
  SWP_NOZORDER     = 0x0004
  SWP_FRAMECHANGED = 0x0020
  HWND_TOP         = 0

  # Retry briefly to ensure the window handle exists after rendering
  for _ in range(10):
    hwnd = ctypes.windll.user32.FindWindowW(None, title)
    if hwnd:
      style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
      style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
      ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
      # Force Windows to flush the style change to the taskbar
      ctypes.windll.user32.SetWindowPos(
        hwnd, HWND_TOP, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
      )
      return
    await asyncio.sleep(0.1)


async def main(page: ft.Page):
  """ Main application Page config and Tracker startup """
  page.padding = 0
  page.spacing = 0
  fixed_width = 300
  fixed_height = 255
  page.title = APP_NAME
  page.window.left = 700
  page.window.opacity = OPACITY
  page.window.frameless = False
  page.window.width = fixed_width
  page.window.skip_task_bar = True
  page.window.always_on_top = True
  page.window.height = fixed_height
  page.window.icon = "favicon.ico" # Windows only
  page.window.min_width = fixed_width
  page.window.max_width = fixed_width
  page.window.title_bar_hidden = True
  page.window.min_height = fixed_height
  page.window.max_height = fixed_height

  # Create asyncio task for continuous tracking/updating outzide of rerender loop
  trak = Tracker()
  trak.get_midnight_timestamp()
  asyncio.create_task(trak.tracker())
  asyncio.create_task(remove_from_taskbar(APP_NAME))

  # Start rendering Subconscious
  return page.render(lambda: AppView(page, trak))

if __name__ == "__main__":
  ft.run(main, assets_dir="./assets")
