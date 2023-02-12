# Debug audio codec ac108 Channel Disorder

## Related Resources

Below are some docs I read when I was trying to solve this problem. 

1. Github issues:
   1. [link](https://github.com/respeaker/seeed-voicecard/issues/301)
   2. [link](https://github.com/respeaker/seeed-voicecard/issues/309)
2. Seeed-voicecard github link: https://github.com/respeaker/seeed-voicecard
3. I also checked forum but there are not useful answers.
4. Driver basics

   1. built-in V.S. module:
      1. https://askubuntu.com/questions/163304/which-device-drivers-are-built-into-the-kernel
   2. device tree:
      1. **https://www.youtube.com/watch?v=a9CZ1Uk3OYQ&ab_channel=Bootlin**
5. Linux ALSA driver basics

   1. [Writing an ALSA Driver](https://www.kernel.org/doc/html/v4.17/sound/kernel-api/writing-an-alsa-driver.html) trigger part
   2. dev_dbg

      1. [How to enable this log? ](https://stackoverflow.com/questions/50504516/enable-linux-kernel-driver-dev-dbg-debug-messages) (use the one from Jeegar)
      2. [basics](https://www.kernel.org/doc/html/v4.15/admin-guide/dynamic-debug-howto.html)
      3. [link](https://github.com/figue/raspberry-pi-kernel/blob/master/Documentation/dynamic-debug-howto.txt)
      



## Test

**Date: 08/21/2022**

**Test List:** 

(1) try to show dev_dbg logs (these logs are useful for debugging the bug)

(2) try to debug the channel disorder problem

**Test device:** 

RPI: DC:A6:32:36:FB:62 raspberry pi 4, password: raspberry

Kernel: Linux raspberrypi 5.4.51-v7l+ #1333 SMP Mon Aug 10 16:51:40 BST 2020 armv7l GNU/Linux, 32bit

Local IP: 192.168.0.104

Current Available logs are from this print function: 

```c
pr_info
```



Test (1) "*try to show dev_dbg logs (these logs are useful for debugging the bug)*"

1. check if config_dynamic_debug is set

   ```
   sudo modprobe configs
   cat /proc/config.gz | gunzip | grep CONFIG_DYNAMIC_DEBUG
   ```

2. We find this flag is not set so we need to recompile the kernel. 

   How to recompile: [link](https://www.raspberrypi.com/documentation/computers/linux_kernel.html)

   My steps (for 32 bit OS) :

   1. Follow the instructions in the above link to install all required tools

   2. ```
      git clone --depth=1 --branch <branch> https://github.com/raspberrypi/linux
      // Choose the correct branch. In my case, I use 5.4.y
      ```

   3. In this step, we will generate a .config file

      In our case, we need to enable dynamic debug, so we go to \arch\arm\configs to change the bcm2711_defconfig. 

      We add CONFIG_DYNAMIC_DEBUG=y at the end of the file

      After executing the following commands, you should see a .config file in your current folder

      ```
      cd linux
      KERNEL=kernel7l
      make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- bcm2711_defconfig
      ```

   4. Compile with this command

      ```
      make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- zImage modules dtbs
      ```

   5. Then we will install it to our sd card

      Just follow the **Install Directly onto the SD Card** session

   6. Install the sd card and power the raspberry pi

   7. check if config_dynamic_debug is set by following the step 1

   8. Sample output

      ```
      pi@raspberrypi:~ $ sudo modprobe configs
      pi@raspberrypi:~ $ cat /proc/config.gz | gunzip | grep CONFIG_DYNAMIC_DEBUG
      CONFIG_DYNAMIC_DEBUG=y
      ```

       Up to now, we successfully recompile and install the new kernel, and the required flag (CONFIG_DYNAMIC_DEBUG) is enabled. 
   
      <span style="color:red">**However, I encountered some problems when I was trying to install the driver. Test 1 failed.**</span>
   
      **(Stop using 9 and 10)**
   
   9. (Does not work) We need to reinstall the driver with this [link](https://github.com/respeaker/seeed-voicecard/tree/rel-v5.5)
   
      ```
      sudo ./install.sh --keep-kernel
      ```
   
   10. (sudo ./install.sh --compat-kernel) Will the install script force us to use the 5.4.51-v7+ ?  ***need to read the script***

One hypothesis: 5.4 + rel-v5.5: clone: from https://github.com/respeaker/seeed-voicecard is a stable version?

#### Test result: 

Linux raspberrypi 5.10.103-v7l+ #1529 SMP Tue Mar 8 12:24:00 GMT 2022 armv7l GNU/Linux +

c526066 **Very unstable**

![image-20220821230423262](C:\Users\beitong2\AppData\Roaming\Typora\typora-user-images\image-20220821230423262.png)

Linux raspberrypi 5.10.110-v7l+ #1 SMP Sun Aug 21 21:00:08 PDT 2022 armv7l GNU/Linux + rel-v5.5 **Cannot compile**

Linux raspberrypi 5.4.83-v7l+ #1 SMP Sun Aug 21 22:28:35 PDT 2022 armv7l GNU/Linux + rel-v5.5 

**Cannot compile**

Linux raspberrypi 5.4.51-v7l+ #1333 SMP Mon Aug 10 16:51:40 BST 2020 armv7l GNU/Linux + rel-v5.5

**Work!**





### Working solution: 

**Result**

![image-20220822105512786](C:\Users\beitong2\AppData\Roaming\Typora\typora-user-images\image-20220822105512786.png)



#### kernel version

```
uname -a
```

**Output:** 

Linux raspberrypi 5.4.51-v7l+ #1333 SMP Mon Aug 10 16:51:40 BST 2020 armv7l GNU/Linux

```
zcat /usr/share/doc/raspberrypi-kernel/changelog.Debian.gz | head
```

**Output:** 

raspberrypi-firmware (**1.20200819-1**) buster; urgency=medium

  * firmware as of ef72c17bcaaeb89093d87bcf71f3228e1b5e1fff
  * Linux version 5.4.51

 -- Serge Schneider <serge@raspberrypi.com>  Thu, 20 Aug 2020 07:56:36 +0100

#### Driver version

With seeed-voice card: 

*commit 8cce4e8ffa77e1e2b89812e5e2ccf6cfbc1086cf (HEAD -> master, origin/rel-v5.5, origin/master, origin/HEAD)* 

Note: this kernel version is the force-kernel version in install.sh

#### How to use this solution

<span style="color:red">(Recommend)</span>

Burn the sd card with client.img. client.img is a raspberry pi image with pre-installed driver. 

Otherwise, we can also install the driver from scratch. In order to install version we need to use 

```
sudo ./install.sh --compat-kernel
```



## TODO

1. Find the kernel and driver version of current sensor array. Work with Cody

   1. The dataset collected before summer. (ssh -p 22 pi@10.193.48.217)

      We use rpi-zero. It uses kernel 5.10 and driver with master branch. (This combination proved to be unworkable)

   2. Check the kernel and driver version of the sensor array (ssh -p 22 pi@10.195.184.172)

      Current status: we cannot ping this rpi4
   
      Solution: Wait for the rpi4 to be online. Otherwise, we need to go to the basement and get it back. 
   
      

## Lesson Learned

1. Before we do any experiments, we need to track information like:
   - the kernel version of rpi
   - the repo version (commit, tag, branch)
   - the mac address of the rpi
   - etc. 