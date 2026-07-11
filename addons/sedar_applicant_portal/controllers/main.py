import base64
import json

from odoo import _, http
from odoo.http import request


MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_MIMETYPES = {
    'application/pdf',
    'image/jpeg',
    'image/png',
}


class SedarApplicantPortal(http.Controller):
    @http.route(
        '/applicant/api/jobs',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
        cors='*',
    )
    def applicant_jobs(self, **kw):
        """Small public contract used by the company careers website."""
        dispatches = request.env['sedar.job.dispatch'].sudo().search(
            [
                ('state', '=', 'approved'),
                ('hr_job_id', '!=', False),
                ('hr_job_id.active', '=', True),
            ],
            order='needed_by asc, requested_datetime desc, id desc',
        )
        jobs = []
        for dispatch in dispatches:
            job = dispatch.hr_job_id
            jobs.append({
                'id': dispatch.id,
                'job_id': job.id if job else False,
                'title': job.name if job else dispatch.role_needed,
                'department': job.department_id.name if job and job.department_id else 'Marine Operations',
                'location': job.address_id.city if job and job.address_id and job.address_id.city else 'Batangas City',
                'type': 'Full-Time',
                'openings': dispatch.quantity,
                'description': dispatch.requirements or dispatch.missing_reason or '',
                'apply_url': '/applicant/apply?dispatch_id=%s' % dispatch.id,
            })
        payload = json.dumps({'jobs': jobs})
        return request.make_response(payload, headers=[('Content-Type', 'application/json')])

    def _layout_context(self):
        lang = request.env.lang or 'en_US'
        return {
            'lang': lang,
            'languages': [(lang, lang, 'English / English')],
        }

    def _safe_int(self, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return False

    def _get_source_records(self, values):
        job = request.env['hr.job']
        dispatch = request.env['sedar.job.dispatch']

        dispatch_id = self._safe_int(values.get('dispatch_id'))
        if dispatch_id:
            dispatch = request.env['sedar.job.dispatch'].sudo().search([
                ('id', '=', dispatch_id),
                ('state', '=', 'approved'),
                ('hr_job_id', '!=', False),
                ('hr_job_id.active', '=', True),
            ], limit=1)
            if dispatch:
                job = dispatch.hr_job_id

        return job, dispatch

    def _render_form(self, values=None, errors=None):
        values = values or {}
        job, dispatch = self._get_source_records(values)
        render_values = {
            'job': job,
            'dispatch': dispatch,
            'values': values,
            'errors': errors or [],
            'max_upload_mb': int(MAX_UPLOAD_SIZE / 1024 / 1024),
        }
        render_values.update(self._layout_context())
        return request.render('sedar_applicant_portal.applicant_apply_form', render_values)

    @http.route('/applicant/apply', type='http', auth='public', methods=['GET'])
    def applicant_apply(self, **kw):
        return self._render_form(values=kw)

    @http.route('/applicant/apply/submit', type='http', auth='public', methods=['POST'])
    def applicant_submit(self, **post):
        values = dict(post)
        job, dispatch = self._get_source_records(values)
        errors = []

        if not job and not dispatch:
            errors.append(_('This application link is missing a valid job source.'))

        required_fields = [
            'family_name', 'given_name', 'middle_name', 'father_name', 'date_of_birth',
            'place_of_birth', 'religion', 'mother_name', 'age', 'height', 'weight',
            'next_of_kin', 'sss_no', 'tin_no', 'philhealth_no', 'pagibig_no',
            'civil_status', 'email', 'telephone', 'mobile', 'city_address',
            'provincial_address', 'sirb_number', 'sirb_date_issued', 'sirb_expiry_date',
            'drivers_license_number', 'drivers_license_date_issued',
            'drivers_license_expiry_date', 'college_school', 'course',
            'education_from', 'education_to', 'english_knowledge',
            'medical_date_exam', 'medical_clinic', 'medical_basic_result',
            'medical_drug_alcohol_result', 'medical_ecg_result', 'legal_case',
            'union_member', 'disability_benefits', 'beneficiary_name',
            'beneficiary_date_of_birth', 'beneficiary_contact_number',
            'beneficiary_address', 'dependent_count', 'notify_name',
            'notify_relationship', 'notify_contact_number', 'notify_address',
            'certification_name', 'certification_date',
        ]
        missing = [field for field in required_fields if not values.get(field)]
        if missing:
            errors.append(_('Please complete all required fields before submitting.'))

        for flag, detail in [
            ('legal_case', 'legal_case_details'),
            ('union_member', 'union_member_details'),
            ('disability_benefits', 'disability_benefits_details'),
        ]:
            if values.get(flag) == 'yes' and not values.get(detail):
                errors.append(_('Please specify details for every Yes answer.'))
                break

        if values.get('certification_agreed') != 'on':
            errors.append(_('Please confirm the certification statement.'))

        self._validate_line_group(
            errors,
            'training_seminar_name',
            ['training_cert_no', 'training_inclusive_dates', 'training_venue', 'training_provider'],
            _('Please complete all training and seminar fields.'),
        )
        self._validate_line_group(
            errors,
            'employment_inclusive_dates',
            ['employment_company_address', 'employment_position', 'employment_reason_leaving'],
            _('Please complete all employment history fields.'),
        )
        self._validate_line_group(
            errors,
            'dependent_name',
            ['dependent_relation', 'dependent_date_of_birth', 'dependent_remarks'],
            _('Please complete all dependent fields.'),
        )

        uploaded_files = self._collect_files(errors)
        if errors:
            return self._render_form(values=values, errors=errors)

        full_name = ' '.join(
            part for part in [
                values.get('given_name'),
                values.get('middle_name'),
                values.get('family_name'),
            ] if part
        )
        applicant_values = {
            'name': _('Application - %s') % full_name,
            'partner_name': full_name,
            'email_from': values.get('email'),
            'partner_phone': values.get('telephone'),
            'partner_mobile': values.get('mobile'),
            'job_id': job.id if job else False,
            'sedar_dispatch_id': dispatch.id if dispatch else False,
            'sedar_target_role': job.name if job else (dispatch.role_needed if dispatch else False),
            'sedar_hiring_state': 'application',
            'description': values.get('certification_statement'),
        }
        applicant = request.env['hr.applicant'].sudo().create(applicant_values)

        profile = request.env['sedar.applicant.profile'].sudo().create(
            self._profile_values(values, applicant)
        )
        self._create_line_records(values, profile)
        attachments = self._create_attachments(uploaded_files, applicant)
        profile.sudo().write({
            'sirb_attachment_id': attachments.get('sirb_attachment'),
            'drivers_license_attachment_id': attachments.get('drivers_license_attachment'),
            'resume_attachment_id': attachments.get('resume_attachment'),
        })

        if 'sedar_dashboard_token' in applicant._fields:
            applicant._sedar_ensure_dashboard_token()
            return request.redirect('/applicant/dashboard/%s?welcome=1' % applicant.sedar_dashboard_token)

        render_values = {'applicant': applicant}
        render_values.update(self._layout_context())
        return request.render('sedar_applicant_portal.applicant_apply_success', render_values)

    def _validate_line_group(self, errors, first_field, companion_fields, message):
        form = request.httprequest.form
        first_values = form.getlist(first_field)
        companion_values = [form.getlist(field) for field in companion_fields]
        if not first_values:
            errors.append(message)
            return

        has_complete_row = False
        for index, first_value in enumerate(first_values):
            row_values = [first_value]
            for values in companion_values:
                row_values.append(values[index] if index < len(values) else '')
            if all(value for value in row_values):
                has_complete_row = True
            elif any(value for value in row_values):
                errors.append(message)
                return
        if not has_complete_row:
            errors.append(message)

    def _collect_files(self, errors):
        files = {}
        for field_name in ['sirb_attachment', 'drivers_license_attachment', 'resume_attachment']:
            uploaded = request.httprequest.files.get(field_name)
            if not uploaded or not uploaded.filename:
                errors.append(_('Please upload all required documents.'))
                continue

            content = uploaded.read()
            uploaded.seek(0)
            if len(content) > MAX_UPLOAD_SIZE:
                errors.append(_('%s exceeds the %s MB upload limit.') % (uploaded.filename, int(MAX_UPLOAD_SIZE / 1024 / 1024)))
                continue
            if uploaded.mimetype not in ALLOWED_MIMETYPES:
                errors.append(_('%s must be a PDF, JPG, or PNG file.') % uploaded.filename)
                continue
            files[field_name] = {
                'filename': uploaded.filename,
                'mimetype': uploaded.mimetype,
                'content': content,
            }
        return files

    def _profile_values(self, values, applicant):
        return {
            'applicant_id': applicant.id,
            'family_name': values.get('family_name'),
            'given_name': values.get('given_name'),
            'middle_name': values.get('middle_name'),
            'father_name': values.get('father_name'),
            'date_of_birth': values.get('date_of_birth'),
            'place_of_birth': values.get('place_of_birth'),
            'religion': values.get('religion'),
            'mother_name': values.get('mother_name'),
            'age': values.get('age'),
            'height': values.get('height'),
            'weight': values.get('weight'),
            'next_of_kin': values.get('next_of_kin'),
            'sss_no': values.get('sss_no'),
            'tin_no': values.get('tin_no'),
            'philhealth_no': values.get('philhealth_no'),
            'pagibig_no': values.get('pagibig_no'),
            'civil_status': values.get('civil_status'),
            'email': values.get('email'),
            'telephone': values.get('telephone'),
            'mobile': values.get('mobile'),
            'city_address': values.get('city_address'),
            'provincial_address': values.get('provincial_address'),
            'sirb_number': values.get('sirb_number'),
            'sirb_date_issued': values.get('sirb_date_issued'),
            'sirb_expiry_date': values.get('sirb_expiry_date'),
            'drivers_license_number': values.get('drivers_license_number'),
            'drivers_license_date_issued': values.get('drivers_license_date_issued'),
            'drivers_license_expiry_date': values.get('drivers_license_expiry_date'),
            'college_school': values.get('college_school'),
            'course': values.get('course'),
            'education_from': values.get('education_from'),
            'education_to': values.get('education_to'),
            'english_knowledge': values.get('english_knowledge'),
            'medical_date_exam': values.get('medical_date_exam'),
            'medical_clinic': values.get('medical_clinic'),
            'medical_basic_result': values.get('medical_basic_result'),
            'medical_drug_alcohol_result': values.get('medical_drug_alcohol_result'),
            'medical_ecg_result': values.get('medical_ecg_result'),
            'legal_case': values.get('legal_case'),
            'legal_case_details': values.get('legal_case_details'),
            'union_member': values.get('union_member'),
            'union_member_details': values.get('union_member_details'),
            'disability_benefits': values.get('disability_benefits'),
            'disability_benefits_details': values.get('disability_benefits_details'),
            'beneficiary_name': values.get('beneficiary_name'),
            'beneficiary_date_of_birth': values.get('beneficiary_date_of_birth'),
            'beneficiary_contact_number': values.get('beneficiary_contact_number'),
            'beneficiary_address': values.get('beneficiary_address'),
            'dependent_count': values.get('dependent_count'),
            'notify_name': values.get('notify_name'),
            'notify_relationship': values.get('notify_relationship'),
            'notify_contact_number': values.get('notify_contact_number'),
            'notify_address': values.get('notify_address'),
            'certification_agreed': values.get('certification_agreed') == 'on',
            'certification_name': values.get('certification_name'),
            'certification_date': values.get('certification_date'),
        }

    def _create_line_records(self, values, profile):
        form = request.httprequest.form
        self._create_lines('sedar.applicant.training', profile, {
            'seminar_name': form.getlist('training_seminar_name'),
            'cert_no': form.getlist('training_cert_no'),
            'inclusive_dates': form.getlist('training_inclusive_dates'),
            'venue': form.getlist('training_venue'),
            'seminar_provider': form.getlist('training_provider'),
        })
        self._create_lines('sedar.applicant.employment', profile, {
            'inclusive_dates': form.getlist('employment_inclusive_dates'),
            'company_address': form.getlist('employment_company_address'),
            'position': form.getlist('employment_position'),
            'reason_leaving': form.getlist('employment_reason_leaving'),
        })
        self._create_lines('sedar.applicant.dependent', profile, {
            'name': form.getlist('dependent_name'),
            'relation': form.getlist('dependent_relation'),
            'date_of_birth': form.getlist('dependent_date_of_birth'),
            'remarks': form.getlist('dependent_remarks'),
        })

    def _create_lines(self, model_name, profile, grouped_values):
        model = request.env[model_name].sudo()
        row_count = max(len(values) for values in grouped_values.values())
        for index in range(row_count):
            vals = {'profile_id': profile.id}
            for field_name, field_values in grouped_values.items():
                vals[field_name] = field_values[index] if index < len(field_values) else False
            if all(value for key, value in vals.items() if key != 'profile_id'):
                model.create(vals)

    def _create_attachments(self, uploaded_files, applicant):
        attachments = {}
        for field_name, file_values in uploaded_files.items():
            attachment = request.env['ir.attachment'].sudo().create({
                'name': file_values['filename'],
                'datas': base64.b64encode(file_values['content']),
                'mimetype': file_values['mimetype'],
                'res_model': 'hr.applicant',
                'res_id': applicant.id,
            })
            attachments[field_name] = attachment.id
        return attachments
