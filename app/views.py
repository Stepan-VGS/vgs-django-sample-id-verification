import json
import os
from datetime import datetime

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, render
from django.conf import settings

from app.checker_client import CheckerClient, CheckerServiceException
from .models import PiiData

vgs_forward_proxy = getattr(settings, "VGS_FORWARD_PROXY", None)


def turn_on_proxy():
    if vgs_forward_proxy is not None:
        os.environ["HTTPS_PROXY"] = vgs_forward_proxy
        os.environ["REQUESTS_CA_BUNDLE"] = os.getcwd() + '/app/cert.pem'


def turn_off_proxy():
    if vgs_forward_proxy is not None:
        del os.environ["HTTPS_PROXY"]
        del os.environ["REQUESTS_CA_BUNDLE"]

def index(request):
    pii_data_list = PiiData.objects.order_by('-pub_date')[:5]
    host = getattr(settings, "VGS_REVERSE_PROXY", "")
    context = {
        'pii_data_list': pii_data_list,
        'host': host
    }
    return render(request, 'app/index.html', context)


def detail(request, data_id):
    pii_data = get_object_or_404(PiiData, pk=data_id)
    host = getattr(settings, "VGS_REVERSE_PROXY", "")
    context = {
        'pii_data': pii_data,
        'host': host
    }
    return render(request, 'app/detail.html', context)


def get_data(request, data_id):
    pii_data = get_object_or_404(PiiData, pk=data_id)
    return HttpResponse(json.dumps({
        'id': pii_data.id,
        'social_security_number': pii_data.social_security_number,
        'driver_license_number': pii_data.driver_license_number,
        'pub_date': pii_data.pub_date,
    }, default=json_serial), content_type="application/json")


def check(request, data_id):
    checkr_api_key = os.environ['CHECKER_API_KEY']
    check_client = CheckerClient(host=settings.CHECKER_HOST, api_key=checkr_api_key)

    pii_data = get_object_or_404(PiiData, pk=data_id)
    try:
        turn_on_proxy()
        candidate_id = check_client.create_candidate(
            ssn=pii_data.social_security_number,
            dln=pii_data.driver_license_number,
        )
        turn_off_proxy()
        report_id = check_client.create_report(candidate_id)
        report = check_client.retrieve_report(report_id)
    except CheckerServiceException as e:
        return HttpResponse(json.dumps({"status_code": e.status_code, "error:": e.error}), content_type="application/json")

    return HttpResponse(json.dumps(report), content_type="application/json")


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))


@csrf_exempt
def add(request):
    snn = request.POST['SNN']
    driver_license_number = request.POST['driver_license_number']
    pii_data = PiiData(social_security_number=snn, driver_license_number=driver_license_number, pub_date=datetime.now())
    pii_data.save()
    return HttpResponse(str(pii_data.id))

