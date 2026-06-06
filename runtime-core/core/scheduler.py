# -*- coding: utf-8 -*-
"""
Pipeline Scheduler
Handles scheduled, event-driven, and dependency-based task execution.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from agents.orchestrator import Orchestrator

class PipelineScheduler:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PipelineScheduler, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.scheduler = BackgroundScheduler()
        self.orchestrator = Orchestrator()
        self._initialized = True
        self._started = False

    def start(self):
        """Start the scheduler safely, avoiding duplicate starts"""
        if not self._started and not self.scheduler.running:
            try:
                self.scheduler.start()
                self._started = True
                logger.info("Pipeline Scheduler started.")
            except Exception as e:
                if "already running" in str(e).lower():
                    logger.warning("Pipeline Scheduler is already running")
                    self._started = True
                else:
                    logger.error("Failed to start Pipeline Scheduler: {}".format(e))
                    raise
        elif self._started:
            logger.info("Pipeline Scheduler already started")
        elif self.scheduler.running:
            logger.info("Pipeline Scheduler is already running")
            self._started = True

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Pipeline Scheduler shut down.")

    def add_scheduled_task(self, task_id, channel_name, config, cron):
        """Add a cron-based scheduled task"""
        self.scheduler.add_job(
            self.orchestrator.run_task,
            CronTrigger.from_crontab(cron),
            args=[task_id, channel_name, config],
            id=task_id,
            replace_existing=True
        )
        logger.info("Added scheduled task: {} with cron: {}".format(task_id, cron))

    def remove_task(self, task_id):
        if self.scheduler.get_job(task_id):
            self.scheduler.remove_job(task_id)
            logger.info("Removed task: {}".format(task_id))

    def trigger_event(self, event_name, payload):
        """Trigger a task based on an event"""
        logger.info("Event triggered: {}".format(event_name))
        # Logic to match event to tasks
        # For example, if event is 'new_mention', run a specific pipeline
        pass

# Global scheduler instance
pipeline_scheduler = PipelineScheduler()
