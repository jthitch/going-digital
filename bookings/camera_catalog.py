"""Camera make/model catalog helpers for booking forms."""
from __future__ import annotations

from bookings.models import CameraMake, CameraModel

CAMERA_CHOICE_UNKNOWN = '__unknown__'
CAMERA_CHOICE_OTHER = '__other__'
CAMERA_LABEL_UNKNOWN = 'Unknown'
CAMERA_LABEL_OTHER = 'Other'


def camera_catalog_for_js():
    """JSON-serialisable catalog for cascading selects."""
    payload = []
    for make in CameraMake.objects.filter(is_active=True).order_by('sort_order', 'name'):
        models = list(
            make.models.filter(is_active=True)
            .order_by('sort_order', 'name')
            .values('id', 'name')
        )
        payload.append({'id': make.pk, 'name': make.name, 'models': models})
    return payload


def make_select_choices():
    choices = [('', 'Select make'), (CAMERA_CHOICE_UNKNOWN, CAMERA_LABEL_UNKNOWN)]
    for make in CameraMake.objects.filter(is_active=True).order_by('sort_order', 'name'):
        choices.append((str(make.pk), make.name))
    choices.append((CAMERA_CHOICE_OTHER, CAMERA_LABEL_OTHER))
    return choices


def model_select_choices(make_choice=''):
    choices = [('', 'Select model'), (CAMERA_CHOICE_UNKNOWN, CAMERA_LABEL_UNKNOWN)]
    if make_choice and make_choice not in {CAMERA_CHOICE_UNKNOWN, CAMERA_CHOICE_OTHER}:
        try:
            make_id = int(make_choice)
        except (TypeError, ValueError):
            make_id = None
        if make_id:
            for model in CameraModel.objects.filter(
                make_id=make_id,
                is_active=True,
            ).order_by('sort_order', 'name'):
                choices.append((str(model.pk), model.name))
    choices.append((CAMERA_CHOICE_OTHER, CAMERA_LABEL_OTHER))
    return choices


def _resolve_make(choice, other_text):
    choice = (choice or '').strip()
    other_text = (other_text or '').strip()
    if not choice:
        return '', ''
    if choice == CAMERA_CHOICE_UNKNOWN:
        return CAMERA_LABEL_UNKNOWN, CAMERA_CHOICE_UNKNOWN
    if choice == CAMERA_CHOICE_OTHER:
        return other_text, CAMERA_CHOICE_OTHER
    try:
        make = CameraMake.objects.get(pk=int(choice), is_active=True)
    except (TypeError, ValueError, CameraMake.DoesNotExist):
        return '', ''
    return make.name, str(make.pk)


def _resolve_model(choice, other_text, *, make_choice):
    choice = (choice or '').strip()
    other_text = (other_text or '').strip()
    if make_choice == CAMERA_CHOICE_UNKNOWN:
        return CAMERA_LABEL_UNKNOWN, CAMERA_CHOICE_UNKNOWN
    if not choice:
        return '', ''
    if choice == CAMERA_CHOICE_UNKNOWN:
        return CAMERA_LABEL_UNKNOWN, CAMERA_CHOICE_UNKNOWN
    if choice == CAMERA_CHOICE_OTHER:
        return other_text, CAMERA_CHOICE_OTHER
    try:
        model = CameraModel.objects.select_related('make').get(pk=int(choice), is_active=True)
    except (TypeError, ValueError, CameraModel.DoesNotExist):
        return '', ''
    return model.name, str(model.pk)


def resolve_camera_selection(make_choice, make_other, model_choice, model_other):
    """Return ``(make_name, model_name, make_choice_key, model_choice_key)``."""
    make_name, make_key = _resolve_make(make_choice, make_other)
    if not make_key:
        return '', '', '', ''
    model_name, model_key = _resolve_model(
        model_choice,
        model_other,
        make_choice=make_key,
    )
    return make_name, model_name, make_key, model_key


def selection_from_stored(make_name, model_name):
    """Map stored booking strings back to select values for editing."""
    make_name = (make_name or '').strip()
    model_name = (model_name or '').strip()
    if not make_name and not model_name:
        return {
            'make_choice': '',
            'make_other': '',
            'model_choice': '',
            'model_other': '',
        }
    if make_name.lower() == CAMERA_LABEL_UNKNOWN.lower():
        return {
            'make_choice': CAMERA_CHOICE_UNKNOWN,
            'make_other': '',
            'model_choice': CAMERA_CHOICE_UNKNOWN,
            'model_other': '',
        }

    make = CameraMake.objects.filter(name__iexact=make_name, is_active=True).first()
    if not make:
        return {
            'make_choice': CAMERA_CHOICE_OTHER,
            'make_other': make_name,
            'model_choice': CAMERA_CHOICE_OTHER,
            'model_other': model_name,
        }

    if not model_name or model_name.lower() == CAMERA_LABEL_UNKNOWN.lower():
        return {
            'make_choice': str(make.pk),
            'make_other': '',
            'model_choice': CAMERA_CHOICE_UNKNOWN if model_name else '',
            'model_other': '',
        }

    model = CameraModel.objects.filter(
        make=make,
        name__iexact=model_name,
        is_active=True,
    ).first()
    if model:
        return {
            'make_choice': str(make.pk),
            'make_other': '',
            'model_choice': str(model.pk),
            'model_other': '',
        }
    return {
        'make_choice': str(make.pk),
        'make_other': '',
        'model_choice': CAMERA_CHOICE_OTHER,
        'model_other': model_name,
    }


def validate_camera_selection(make_choice, make_other, model_choice, model_other, *, required):
    """Return dict of field errors keyed by camera_make / camera_model."""
    make_choice = (make_choice or '').strip()
    make_other = (make_other or '').strip()
    model_choice = (model_choice or '').strip()
    model_other = (model_other or '').strip()
    errors = {}

    if not make_choice:
        if required:
            errors['camera_make'] = 'Camera make is required.'
        return errors

    if make_choice == CAMERA_CHOICE_OTHER and not make_other:
        errors['camera_make'] = 'Please enter the camera make.'
        return errors

    _make_name, make_key = _resolve_make(make_choice, make_other)
    if not make_key:
        errors['camera_make'] = 'Select a valid camera make.'
        return errors

    if make_key == CAMERA_CHOICE_UNKNOWN:
        return errors

    if not model_choice:
        if required:
            errors['camera_model'] = 'Camera model is required.'
        return errors

    if model_choice == CAMERA_CHOICE_OTHER and not model_other:
        errors['camera_model'] = 'Please enter the camera model.'
        return errors

    _model_name, model_key = _resolve_model(
        model_choice,
        model_other,
        make_choice=make_key,
    )
    if not model_key:
        errors['camera_model'] = 'Select a valid camera model.'
    elif (
        model_key not in {CAMERA_CHOICE_UNKNOWN, CAMERA_CHOICE_OTHER}
        and make_key not in {CAMERA_CHOICE_UNKNOWN, CAMERA_CHOICE_OTHER}
    ):
        try:
            model = CameraModel.objects.get(pk=int(model_key))
            if str(model.make_id) != make_key:
                errors['camera_model'] = 'Select a model for the chosen make.'
        except (TypeError, ValueError, CameraModel.DoesNotExist):
            errors['camera_model'] = 'Select a valid camera model.'
    return errors
