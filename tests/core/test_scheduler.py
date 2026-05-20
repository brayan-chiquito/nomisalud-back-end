"""Tests del planificador APScheduler (SCRUM-180)."""

from unittest.mock import MagicMock, patch

from app.core.scheduler import detener_scheduler, iniciar_scheduler


def test_iniciar_scheduler_deshabilitado() -> None:
    detener_scheduler()
    with patch("app.core.scheduler.get_settings") as mock_settings:
        mock_settings.return_value.SCHEDULER_ENABLED = False
        assert iniciar_scheduler() is None


def test_iniciar_scheduler_registra_job_07_00() -> None:
    detener_scheduler()
    with (
        patch("app.core.scheduler.get_settings") as mock_settings,
        patch("app.core.scheduler.AsyncIOScheduler") as mock_cls,
    ):
        s = mock_settings.return_value
        s.SCHEDULER_ENABLED = True
        s.SCHEDULER_TIMEZONE = "America/Bogota"
        s.SCHEDULER_CRON_HOUR = 7
        s.SCHEDULER_CRON_MINUTE = 0
        inst = MagicMock()
        mock_cls.return_value = inst
        iniciar_scheduler()
        inst.add_job.assert_called_once()
        call_kw = inst.add_job.call_args.kwargs
        assert call_kw["id"] == "revision_vencimientos_diaria"
        inst.start.assert_called_once()
    detener_scheduler()
