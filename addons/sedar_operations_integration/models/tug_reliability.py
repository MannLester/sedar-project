from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SedarTugSchedule(models.Model):
    _inherit = 'sedar.tug.schedule'

    @api.constrains('start_datetime', 'end_datetime')
    def _check_schedule_dates(self):
        for schedule in self:
            if schedule.end_datetime and schedule.end_datetime <= schedule.start_datetime:
                raise ValidationError('The schedule end must be after its start.')

    @api.constrains('vessel_id', 'start_datetime', 'end_datetime', 'state')
    def _check_vessel_schedule_overlap(self):
        for schedule in self.filtered(
            lambda item: item.state in ('confirmed', 'in_progress') and item.end_datetime
        ):
            overlap = self.search_count([
                ('id', '!=', schedule.id),
                ('vessel_id', '=', schedule.vessel_id.id),
                ('state', 'in', ('confirmed', 'in_progress')),
                ('start_datetime', '<', schedule.end_datetime),
                '|',
                ('end_datetime', '=', False),
                ('end_datetime', '>', schedule.start_datetime),
            ])
            if overlap:
                raise ValidationError('This vessel already has an active assignment during that time.')

    def action_confirm(self):
        if any(not schedule.end_datetime for schedule in self):
            raise UserError('Set the schedule end before confirming the assignment.')
        return super().action_confirm()

    def action_start(self):
        if any(not schedule.end_datetime for schedule in self):
            raise UserError('Set the schedule end before starting the assignment.')
        return super().action_start()


class SedarVoyageLog(models.Model):
    _inherit = 'sedar.voyage.log'

    duration_hours = fields.Float(compute='_compute_duration_hours', store=True)

    @api.depends('departure_time', 'arrival_time')
    def _compute_duration_hours(self):
        for voyage in self:
            voyage.duration_hours = (
                (voyage.arrival_time - voyage.departure_time).total_seconds() / 3600
                if voyage.departure_time and voyage.arrival_time
                else 0.0
            )

    @api.constrains('departure_time', 'arrival_time', 'distance_nm')
    def _check_voyage_values(self):
        for voyage in self:
            if voyage.arrival_time and voyage.departure_time and voyage.arrival_time < voyage.departure_time:
                raise ValidationError('Voyage arrival cannot be before departure.')
            if voyage.distance_nm < 0:
                raise ValidationError('Voyage distance cannot be negative.')


class SedarFuelLog(models.Model):
    _inherit = 'sedar.fuel.log'

    @api.constrains('liters', 'cost')
    def _check_fuel_values(self):
        for fuel_log in self:
            if fuel_log.liters <= 0:
                raise ValidationError('Fuel quantity must be greater than zero.')
            if fuel_log.cost < 0:
                raise ValidationError('Fuel cost cannot be negative.')


class SedarVesselTrackingLog(models.Model):
    _inherit = 'sedar.vessel.tracking.log'

    @api.constrains('latitude', 'longitude', 'speed_knots', 'course_degrees', 'timestamp')
    def _check_tracking_values(self):
        future_limit = fields.Datetime.now() + timedelta(minutes=10)
        for tracking in self:
            if not -90 <= tracking.latitude <= 90:
                raise ValidationError('Latitude must be between -90 and 90 degrees.')
            if not -180 <= tracking.longitude <= 180:
                raise ValidationError('Longitude must be between -180 and 180 degrees.')
            if tracking.speed_knots < 0:
                raise ValidationError('Vessel speed cannot be negative.')
            if not 0 <= tracking.course_degrees < 360:
                raise ValidationError('Vessel course must be from 0 up to, but not including, 360 degrees.')
            if tracking.timestamp > future_limit:
                raise ValidationError('Tracking time cannot be more than ten minutes in the future.')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped('vessel_id')._sedar_refresh_latest_position()
        return records

    def write(self, values):
        vessels = self.mapped('vessel_id')
        result = super().write(values)
        (vessels | self.mapped('vessel_id'))._sedar_refresh_latest_position()
        return result

    def unlink(self):
        vessels = self.mapped('vessel_id')
        result = super().unlink()
        vessels._sedar_refresh_latest_position()
        return result


class SedarVessel(models.Model):
    _inherit = 'sedar.vessel'

    def _sedar_refresh_latest_position(self):
        tracking_model = self.env['sedar.vessel.tracking.log']
        for vessel in self:
            latest = tracking_model.search([('vessel_id', '=', vessel.id)], order='timestamp desc, id desc', limit=1)
            vessel.write({
                'current_latitude': latest.latitude if latest else 0.0,
                'current_longitude': latest.longitude if latest else 0.0,
                'speed_knots': latest.speed_knots if latest else 0.0,
                'course_degrees': latest.course_degrees if latest else 0.0,
                'last_position_at': latest.timestamp if latest else False,
            })
