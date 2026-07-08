import base64

from odoo import _, http
from odoo.http import request
from werkzeug.exceptions import NotFound
from werkzeug.utils import secure_filename


MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_MIMETYPES = {
    'application/pdf',
    'image/jpeg',
    'image/png',
}


class SedarApplicantDashboard(http.Controller):
    def _layout_context(self):
        lang = request.env.lang or 'en_US'
        return {
            'lang': lang,
            'languages': [(lang, lang, 'English / English')],
        }

    def _get_applicant(self, token):
        applicant = request.env['hr.applicant'].sudo().search(
            [('sedar_dashboard_token', '=', token)],
            limit=1,
        )
        if not applicant:
            raise NotFound()
        applicant._sedar_ensure_dashboard_token()
        return applicant

    def _profile(self, applicant):
        return applicant.sedar_applicant_profile_ids[:1]

    def _public_status(self, applicant):
        labels = {
            'application': _('Application Received'),
            'for_interview': _('Interview Stage'),
            'final_assessment': _('Final Assessment'),
            'contract_signing': _('Contract Signing'),
            'hired': _('Completed'),
        }
        return labels.get(applicant.sedar_hiring_state, _('Under Review'))

    def _progress_steps(self, applicant):
        order = [
            ('application', _('Application Submitted')),
            ('review', _('HR Review')),
            ('for_interview', _('Interview')),
            ('final_assessment', _('Final Assessment')),
            ('contract_signing', _('Contract Signing')),
            ('hired', _('Completed')),
        ]
        state_rank = {
            'application': 1,
            'for_interview': 3,
            'final_assessment': 4,
            'contract_signing': 5,
            'hired': 6,
        }.get(applicant.sedar_hiring_state, 2)
        return [
            {
                'key': key,
                'label': label,
                'is_done': index + 1 < state_rank,
                'is_current': index + 1 == state_rank,
            }
            for index, (key, label) in enumerate(order)
        ]

    def _document_rows(self, applicant, profile):
        rows = []
        if profile:
            rows.extend([
                self._document_row(_('Resume'), profile.resume_attachment_id),
                self._document_row(_('SIRB'), profile.sirb_attachment_id, profile.sirb_expiry_date),
                self._document_row(_("Driver's License"), profile.drivers_license_attachment_id, profile.drivers_license_expiry_date),
            ])
            rows.append({
                'name': _('Medical'),
                'status': _('Submitted') if profile.medical_date_exam else _('Missing'),
                'status_class': 'is-submitted' if profile.medical_date_exam else 'is-missing',
                'detail': profile.medical_clinic or '',
                'attachment': False,
                'expiry_date': False,
            })
        else:
            rows.extend([
                self._missing_document(_('Resume')),
                self._missing_document(_('SIRB')),
                self._missing_document(_("Driver's License")),
                self._missing_document(_('Medical')),
            ])

        base_attachment_ids = [row['attachment'].id for row in rows if row.get('attachment')]
        extra_attachments = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'hr.applicant'),
            ('res_id', '=', applicant.id),
            ('id', 'not in', base_attachment_ids or [0]),
        ], order='create_date desc, id desc')
        for attachment in extra_attachments:
            rows.append(self._document_row(attachment.name, attachment))
        return rows

    def _document_row(self, name, attachment, expiry_date=False):
        return {
            'name': name,
            'status': _('Submitted') if attachment else _('Missing'),
            'status_class': 'is-submitted' if attachment else 'is-missing',
            'detail': attachment.name if attachment else '',
            'attachment': attachment,
            'expiry_date': expiry_date,
        }

    def _missing_document(self, name):
        return self._document_row(name, False)

    @http.route('/applicant/dashboard/<string:token>', type='http', auth='public', methods=['GET'])
    def applicant_dashboard(self, token, upload_status=None, **kw):
        applicant = self._get_applicant(token)
        profile = self._profile(applicant)
        values = {
            'applicant': applicant,
            'profile': profile,
            'public_status': self._public_status(applicant),
            'progress_steps': self._progress_steps(applicant),
            'document_rows': self._document_rows(applicant, profile),
            'upload_status': upload_status,
            'max_upload_mb': int(MAX_UPLOAD_SIZE / 1024 / 1024),
        }
        values.update(self._layout_context())
        return request.render('sedar_applicant_dashboard.applicant_dashboard', values)

    @http.route('/applicant/dashboard/<string:token>/documents/upload', type='http', auth='public', methods=['POST'])
    def applicant_dashboard_upload(self, token, **post):
        applicant = self._get_applicant(token)
        upload = request.httprequest.files.get('document')
        status = 'missing'
        if upload and upload.filename:
            content = upload.read()
            upload.seek(0)
            if len(content) > MAX_UPLOAD_SIZE:
                status = 'too_large'
            elif upload.mimetype not in ALLOWED_MIMETYPES:
                status = 'invalid_type'
            else:
                safe_name = secure_filename(upload.filename) or upload.filename
                request.env['ir.attachment'].sudo().create({
                    'name': safe_name,
                    'datas': base64.b64encode(content),
                    'mimetype': upload.mimetype,
                    'res_model': 'hr.applicant',
                    'res_id': applicant.id,
                    'description': post.get('description'),
                })
                status = 'uploaded'
        return request.redirect('/applicant/dashboard/%s?upload_status=%s' % (token, status))

    @http.route('/applicant/dashboard/<string:token>/documents/<int:attachment_id>', type='http', auth='public', methods=['GET'])
    def applicant_dashboard_document(self, token, attachment_id, **kw):
        applicant = self._get_applicant(token)
        attachment = request.env['ir.attachment'].sudo().browse(attachment_id).exists()
        if not attachment or attachment.res_model != 'hr.applicant' or attachment.res_id != applicant.id:
            raise NotFound()

        content = base64.b64decode(attachment.datas or b'')
        headers = [
            ('Content-Type', attachment.mimetype or 'application/octet-stream'),
            ('Content-Disposition', 'attachment; filename="%s"' % attachment.name.replace('"', '')),
        ]
        return request.make_response(content, headers)
