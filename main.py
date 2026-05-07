import os
import json
import psutil
import asyncio
import logging
import datetime
import flet as ft
import flet_charts as fch


logger = logging.getLogger("data_trakr")
DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "network_data.json")


class Tracker:
  """ Handles the data tracking and storage """
  ready = False # Indicates if Tracker is ready

  def __init__(self):
    self.start_sent, self.start_recv, self.hourly_data = self.load_data()

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
            return data.get("sent", 0), data.get("recv", 0), data.get("hourly", [0.0] * 24)
      except Exception as e:
        logger.error(f"Error loading data: {e}")

    return 0, 0, [0.0] * 24

  def save_data(self, sent, recv, last_sent, last_recv, hourly):
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
            "hourly": hourly
          },
          f
        )
    except Exception as e:
      logger.error(f"Error saving data: {e}")
  
  def setup(self, set_sent, set_recv, set_total, set_hourly) -> None:
    """ Setup the state variables """
    self.set_sent = set_sent
    self.set_recv = set_recv
    self.set_total = set_total
    self.set_hourly = set_hourly
    self.ready = True

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
      
      self.save_data(total_sent, total_recv, last_sent, last_recv, hourly)

      await asyncio.sleep(10)  # update every 10 seconds

def _build_hourly_chart(hourly: list[float]) -> fch.BarChart:
  """ Build a 24-bar chart showing hourly network usage in MB """
  max_y = 100
  current_hour = datetime.datetime.now().hour
  max_mb = max((v / (1024 * 1024) for v in hourly), default=0)

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
  total, set_total = ft.use_state(trak.start_sent + trak.start_recv)
  hourly, set_hourly = ft.use_state(list(trak.hourly_data))

  # Setup the tracker for start
  trak.setup(set_sent, set_recv, set_total, set_hourly)

  # Opacity update event handlers
  def mouse_enter(e):
    page.window.opacity = 1
    page.update()
  
  def mouse_exit(e):
    page.window.opacity = 0.5
    page.update()

  return [
    ft.GestureDetector(
      ft.WindowDragArea(
        ft.Container(
          ft.Column(
            [
              ft.Container(
                ft.Row(
                  [
                    ft.Text(
                      size=18,
                      expand=True,
                      value="Data Tracker",
                      # color=ft.Colors.BLUE,
                      weight=ft.FontWeight.BOLD,
                      text_align=ft.TextAlign.CENTER,
                      margin=ft.Margin.all(0)

                    )
                  ],
                  expand=True,
                ),
                padding=ft.Padding.symmetric(vertical=10, horizontal=0),
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
                content=_build_hourly_chart(hourly),
                padding=ft.Padding.symmetric(horizontal=4, vertical=10),
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

async def main(page: ft.Page):
  """ Main application Page config and Tracker startup """
  page.padding = 0
  page.spacing = 0
  fixed_width = 300
  fixed_height = 210
  page.window.left = 700
  page.window.opacity = 0.5
  page.title = "Data Traker"
  page.window.frameless = False
  page.window.width = fixed_width
  page.window.skip_task_bar = True
  page.window.always_on_top = True
  page.window.height = fixed_height
  page.window.min_width = fixed_width
  page.window.max_width = fixed_width
  page.window.title_bar_hidden = True
  page.window.min_height = fixed_height
  page.window.max_height = fixed_height
  # page.window.icon = "favicon.ico" # Windows only

  # Create asyncio task for continuous tracking/updating outzide of rerender loop
  trak = Tracker()
  trak.get_midnight_timestamp()
  asyncio.create_task(trak.tracker())

  # Start rendering Subconscious
  return page.render(lambda: AppView(page, trak))

if __name__ == "__main__":
  ft.run(main, assets_dir="../assets")
