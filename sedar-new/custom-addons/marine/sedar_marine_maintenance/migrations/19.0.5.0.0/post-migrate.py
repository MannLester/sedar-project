from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    cr.execute(
        """
        UPDATE sedar_daily_engine_report report
           SET watch_start = line.time_start, watch_stop = line.time_stop
          FROM (
              SELECT DISTINCT ON (report_id) report_id, time_start, time_stop
                FROM sedar_daily_engine_report_line
               WHERE hours_run > 0
               ORDER BY report_id, id
          ) line
         WHERE line.report_id = report.id
        """
    )
    cr.execute(
        """
        UPDATE sedar_daily_engine_report_line
           SET fuel_rob_stop = COALESCE(fuel_rob, 0),
               fuel_rob_start = COALESCE(fuel_rob, 0) + COALESCE(fuel_consumed, 0),
               engine_status = CASE WHEN hours_run > 0 THEN 'operated' ELSE 'standby' END
         WHERE fuel_rob_stop IS NULL
        """
    )
    env = api.Environment(cr, SUPERUSER_ID, {})
    reports = env["sedar.daily.engine.report"].search([])
    env.add_to_compute(reports._fields["name"], reports)
    env.flush_all()
