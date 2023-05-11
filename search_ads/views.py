from django.shortcuts import render
from django.http import JsonResponse
from .forms import HrSiteAccountForm, HrSiteAdvForm
from .models import HrSiteReport, HrSiteAdv, HrSiteAccount
from .search_sites import *
from django.utils import timezone
from requests_html import HTMLSession
from django.shortcuts import redirect
from selenium import webdriver
from pyvirtualdisplay import Display
from datetime import datetime


def create_hr_report(request):
    if request.method == "POST":
        results = search(request)
    else:
        results = []
    print(results)
    accounts = []
    for row in HrSiteAccount.objects.all().order_by("name"):
        accounts.append({"name": row.name, "phone": row.phone})
    return render(request, 'create_hr_site_report.html', {'data': results, "accounts": accounts})


def search(request):
    data = request.POST
    try:
        print(data)
    except UnicodeEncodeError:
        request.encoding = "utf-8"
        data = request.POST
        print(data)
    results = []
    keywords = data.getlist('keywords')
    print(keywords)
    mnames = data.getlist('managers')
    if 'in_vacancies' in data.keys():
        in_vacancies=data['in_vacancies']
    else:
        in_vacancies = 'no'
    accounts = []
    for mname in mnames:
        accounts.extend(HrSiteAccount.objects.filter(name=mname))
    if 'pagenum' in data.keys():
        pagenum = data['pagenum']
    else:
        pagenum = 5
    sites = data.getlist('site[]')
    if 'maxpos' in data.keys():
        maxpos=int(data['maxpos'])
    else:
        maxpos=20
    key = int(data['key'])

    report = HrSiteReport()
    report.create_time = timezone.now()
    report.key = key
    report.positionCount = maxpos
    report.sites = ", ".join(sites)
    report.managers = ", ".join([account.name + " (" + account.phone + ")" for account in accounts])
    report.current_status = 'Подготовка...'
    report.save()

    display = None
    if "avito" in sites or "jobmo" in sites:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)
        driver = webdriver.Chrome(executable_path="/usr/bin/chromedriver", chrome_options=options)
    else:
        driver = None
    if "avito" in sites:
        avito_res = search_avito(driver, keywords, accounts, pagenum, maxpos,report,in_vacancies)
        results.extend(avito_res)
    if "birge" in sites:
        birge_res = search_birge(keywords, accounts, pagenum, maxpos,report)
        results.extend(birge_res)
    if "rabota" in sites:
        rabota_res = search_rabota(keywords, accounts, pagenum, maxpos,report)
        results.extend(rabota_res)
    if "jerdesh" in sites:
        jerdesh_res = search_jerdesh(keywords, accounts, pagenum, maxpos,report)
        results.extend(jerdesh_res)
    if "jobmo" in sites:
        jobmo_res = search_jobmo(driver, keywords, accounts, pagenum, maxpos,report)
        results.extend(jobmo_res)
    report.current_status = 'Поиск завершен'
    report.save()
    if driver is not None:
        driver.close()
    if 'save' in data.keys():
        print("saving ads")
        for row in results:
            print(row)
            row.report = report
            row.save()
    else:
        report.delete()
    if display is not None:
        display.stop()
    return JsonResponse({"ads":[result.get_dict() for result in results] })


def get_report_status(request):
    key = request.GET.get('key') or None
    report = HrSiteReport.objects.filter(key=int(key)).first()

    if report:
        return JsonResponse({'status': report.current_status})
    else:
        return JsonResponse(status=400, data={})


def byPos(item):
    return item['position']


def show_hr_reports(request):
    request.encoding = "utf-8"
    ads = []  # HrSiteAdv.objects.all().order_by("-report__pk")
    reports = HrSiteReport.objects.all().order_by("-pk")
    for report in reports:
        rep_ads = HrSiteAdv.objects.filter(report__pk=report.pk)
        if not rep_ads:
            ads.append({
                'report': report.get_dict(),
                'title': 'Нет объявлений',
                'keyword': '-',
                'position': '-',
                'site': '-',
                'account': {'name': '-', 'phone': '-'}
            })
        else:
            rep_ads = [rep_ad.get_dict() for rep_ad in rep_ads]
            for ad in rep_ads:
                ad['report'] = report.get_dict()
            ads.extend(rep_ads)
    # return render(request, 'hr_reports.html', {'ads': ads})

    return JsonResponse({'ads': ads})


def new_hr_account(request):
    request.encoding = "utf-8"
    print("new account")
    message = ""
    if request.method == "POST":
        print(request.POST)
        form = HrSiteAccountForm(request.POST)
        if form.is_valid:
            form.save()
            success = True
            print(form.cleaned_data)
            message = form.cleaned_data['name']+", "+form.cleaned_data['phone']
        else:
            success = False
            message = "Неправильные данные"
    else:
        success = True
    return JsonResponse({"success": success, "message": message})
    # render(request, "new_hr_site_account.html", {'сform': form})


def hr_site_accounts(request):
    accounts = HrSiteAccount.objects.all().order_by("name")
    data = []
    for account in accounts:
        data.append({'name': account.name, 'phone': account.phone})
    print(len(data))
    return JsonResponse({'accounts': data})  # render(request, "hr_site_accounts.html", {'accounts': accounts})
