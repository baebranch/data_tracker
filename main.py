import os
import json
import psutil
import asyncio
import logging
import datetime
import flet as ft


logger = logging.getLogger("data_trakr")
DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "network_data.json")


class Tracker:
  """ Handles the data tracking and storage """
  ready = False # Indicates if Tracker is ready

  def __init__(self):
    self.start_sent, self.start_recv = self.load_data()

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
            return data.get("sent", 0), data.get("recv", 0)
      except Exception as e:
        logger.error(f"Error loading data: {e}")

    return 0, 0

  def save_data(self, sent, recv, last_sent, last_recv):
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
            "last_recv": last_recv
          },
          f
        )
    except Exception as e:
      logger.error(f"Error saving data: {e}")
  
  def setup(self, set_sent, set_recv, set_total) -> None:
    """ Setup the state variables """
    self.set_sent = set_sent
    self.set_recv = set_recv
    self.set_total = set_total
    self.ready = True

  # async def tracker(accumulated_sent, accumulated_recv, set_sent, set_total, set_recv) -> None:
  async def tracker(self) -> None:
    """ Tracks additional data sent """
    counters = psutil.net_io_counters()
    last_sent = counters.bytes_sent
    last_recv = counters.bytes_recv
    
    total_sent = self.start_sent
    total_recv = self.start_recv
    
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    # Continuosly track data usage
    while True:
      # Get current bytes sent and current day
      counters = psutil.net_io_counters()
      current_today_str = datetime.datetime.now().strftime("%Y-%m-%d")

      # If day has rolled over, reset all counters
      if current_today_str != today_str:
        # Set new current day string and totals to zero
        today_str = current_today_str
        total_sent = 0
        total_recv = 0

      # Calculate deltas, increment toals and reset last
      delta_sent = counters.bytes_sent - last_sent
      delta_recv = counters.bytes_recv - last_recv

      if delta_sent < 0:
        delta_sent = counters.bytes_sent
      if delta_recv < 0:
        delta_recv = counters.bytes_recv

      total_sent += delta_sent
      total_recv += delta_recv

      last_sent = counters.bytes_sent
      last_recv = counters.bytes_recv
      
      # Set state variables
      self.set_sent(total_sent)
      self.set_recv(total_recv)
      self.set_total(total_sent + total_recv)
      
      self.save_data(total_sent, total_recv, last_sent, last_recv)

      await asyncio.sleep(10)  # update every 10 seconds

@ft.component
def AppView(page: ft.Page, trak: Tracker) -> list[ft.Control]:
  """ Main application view - manages layout and global state """
  # Create tracker state variables
  sent, set_sent = ft.use_state(trak.start_sent)
  recv, set_recv = ft.use_state(trak.start_recv)
  total, set_total = ft.use_state(trak.start_sent + trak.start_recv)

  # Setup the tracker for start
  trak.setup(set_sent, set_recv, set_total)

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
                expand=True
              ),
              ft.Column(
                [
                  ft.Row(
                    [
                      # Sent
                      ft.Text(
                        f"Sent: {sent / (1024*1024):.2f} MB",
                        text_align=ft.TextAlign.CENTER,
                        weight=ft.FontWeight.BOLD,
                        expand=True
                      ),

                      # Received
                      ft.Text(
                        f"Recv: {recv / (1024*1024):.2f} MB",
                        text_align=ft.TextAlign.CENTER,
                        weight=ft.FontWeight.BOLD,
                        expand=True
                      )
                    ],
                    expand=True
                  ),

                  ft.Row(
                    [
                      # Total
                      ft.Text(
                        f"Total: {total / (1024*1024):.2f} MB",
                        text_align=ft.TextAlign.CENTER,
                        weight=ft.FontWeight.BOLD,
                        expand=True
                      )
                    ],
                    expand=True
                  ),
                ],
                expand=True,
                alignment=ft.MainAxisAlignment.CENTER
              ),

              # Usage chart
              ft.Container(
              )
            ],
            spacing=0,
            expand=True
          ),
          height=120,
          expand=True,
          border_radius=20,
          bgcolor=ft.Colors.SURFACE,
          padding=ft.Padding.only(bottom=15),
          animate_opacity=ft.Animation(
            duration=200,
            curve=ft.AnimationCurve.EASE_IN_OUT
          )
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
  page.window.left = 700
  page.window.width = 300
  page.window.height = 220
  page.window.opacity = 0.5
  page.title = "Data Trakr"
  page.window.min_width = 300
  page.window.max_width = 300
  page.window.min_height = 220
  page.window.max_height = 220
  page.window.frameless = False
  page.window.skip_task_bar = True
  page.window.always_on_top = True
  # page.window.icon = "favicon.ico" # Windows only
  page.window.title_bar_hidden = True

  # Create asyncio task for continuous tracking/updating outzide of rerender loop
  trak = Tracker()
  trak.get_midnight_timestamp()
  asyncio.create_task(trak.tracker())

  # Start rendering Subconscious
  return page.render(lambda: AppView(page, trak))

if __name__ == "__main__":
  ft.run(main, assets_dir="../assets")
