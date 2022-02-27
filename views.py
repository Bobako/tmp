from django.shortcuts import (
    render,
    redirect
)
from django.http import (
    Http404,
    JsonResponse
)
from django.db.models import Q

# It's custom library not from 'pypi'
#from insta_meter import InstaMeter
from .helpers import *
from .models import *

import datetime
import time
import requests
import json, pickle

import ig_parser


def index(request):
    if not checkForStaff(request.user):
        return redirect('admin:index')

    return render(request, 'site/index.html')


def postsPage(request):
    if not checkForStaff(request.user):
        raise Http404

    data = request.GET
    
    sbm_type = data.get("sbm_type")
    if not sbm_type:
        raise Http404

    username = data.get("username")
    if not username:
        raise Http404

    TYPE_CHOICE = ['posts', 'likes', 'comments']
    if sbm_type not in TYPE_CHOICE:
        raise Http404


    context = {
        "sbm_type": sbm_type,
        "username": username,
        "starting": data.get("starting"),
        "end": data.get("end"),
        "order": data.get("order", "desc"),
    }

    return render(request, "site/postspage.html", context, )


def getAlbumUrls(request):
    if not checkForStaff(request.user):
        return JsonResponse({"data": {
            "status": "failed",
            "message": "Permission denied."
        }})
    
    data = request.GET
    shortcode = data.get("shortcode")

    if not shortcode:
        return JsonResponse({"data": {
            "status": "success",
            "urls": []
        }})
    proxy_url = Constant.objects.get(key="PROXY_URL").value
    proxies = {
            "http": proxy_url,
            "https": proxy_url,
    }
    print(proxies)
    urls = []
    try:
        if proxy_url != '':
            resp = requests.get(f"https://www.instagram.com/p/{shortcode}/?__a=1", proxies=proxies)
        else:
            resp = requests.get(f"https://www.instagram.com/p/{shortcode}/?__a=1")
        resp_json = resp.json()
        
        for edge in resp_json['graphql']['shortcode_media']['edge_sidecar_to_children']['edges']:
            urls.append(edge["node"]["display_url"])
    except:
        try:
            urls.append(resp.json()['graphql']['shortcode_media']['video_url'])
        except:
            urls.append(resp.json()["graphql"]["shortcode_media"]["display_url"])


    return JsonResponse({"data": {
        "status": "success",
        "urls": urls,
    }})


def postPreparing(request):
    if not checkForStaff(request.user):
        return JsonResponse({"data": {
            "status": "failed",
            "message": "Permission denied.",
        }})

    data = request.GET
    sbm_type = data.get("sbm_type")
    username = data.get("username")
    start = data.get("starting")
    end = data.get("end")
    order = data.get("order")
    if start:
        try:
            start = time.mktime(datetime.datetime.strptime(start, "%d.%m.%Y").timetuple())
        except Exception as ex:
            start = None

    if end:
        try:
            end = time.mktime((datetime.datetime.strptime(end, "%d.%m.%Y")+datetime.timedelta(days=1)).timetuple())
        except Exception as ex:
            end = None

    posts, stats = ig_parser.get_posts(username, start, end, sbm_type, order)
    insta_post_url = "https://instagram.com/p/{0}/"
    for post in posts:
        post_url = insta_post_url.format(post["code"])

        try:        
            mark = Mark.objects.get(post_addr=post_url)
            time_marked = str(mark.marked_time)
            post["mark"] = time_marked
        except:
            pass

    return JsonResponse({
        "data": {
            "info": {
                "username": username,
                "start": start,
                "end": end,
            },
            "stats": stats,
            "posts": posts,
        }
    }) 


def addMark(request):
    if not checkForStaff(request.user):
        return JsonResponse({
            "data": {
                "status": "failed",
                "message": "Permission denied.",
            }
        })
    
    data = request.GET
    
    username = data.get("username")
    post_addr = data.get("post_addr")

    try:
        mark = Mark.objects.get(post_addr=post_addr)
        mark.delete()
        message = "Mark deleted successfuly."
        action = "delete"
    except:
        new_mark = Mark()
        new_mark.username = username
        new_mark.post_addr = post_addr
        new_mark.save()
        message = "Added successfully."
        action = "add"

    return JsonResponse({"data": {
        "status": "success",
        "message": message, 
        "action": action,
    }})


def checkForStaff(user):
    #return True
    if user.is_staff:
        return True
    return False
