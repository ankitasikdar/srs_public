#!/usr/bin/env python

import roslib
roslib.load_manifest('srs_grasping')
import rospy
import sys, time
#import openravepy

from xml.dom import minidom
from numpy import *

from tf.transformations import *
from trajectory_msgs.msg import *
from geometry_msgs.msg import *
from srs_grasping.msg import *

from simple_script_server import *
sss = simple_script_server()

pi = math.pi
package_path = roslib.packages.get_pkg_dir('srs_grasping')


#################################################################################################
class GraspConfig(): ############################################################################
#################################################################################################

	def __init__(self, joint_values, GraspPose, MinDist, Volume):
		self.joint_values = joint_values
		self.GraspPose = GraspPose
		self.MinDist = MinDist
		self.Volume = Volume

	
	def __cmp__(self,other):
		
		if self.Volume > other.Volume:
			return 1
		elif self.Volume < other.Volume:
			return -1
		else:
			return 0
		

	###### [ GRASP CMP FILTERS ] ##################################################
	def Z(self,other):
		s = self.GraspPose.pose.position.z
		o = other.GraspPose.pose.position.z

		if s > o:
			return 1
		elif  s < o:
			return -1
		else:
			return 0


	def _Z(self,other):
		s = self.GraspPose.pose.position.z
		o = other.GraspPose.pose.position.z

		if s > o:
			return -1
		elif  s < o:
			return 1
		else:
			return 0


	def X(self,other):
		s = self.GraspPose.pose.position.x
		o = other.GraspPose.pose.position.x

		if s > o:
			return 1
		elif  s < o:
			return -1
		else:
			return 0


	def _X(self,other):
		s = self.GraspPose.pose.position.x
		o = other.GraspPose.pose.position.x

		if s > o:
			return -1
		elif  s < o:
			return 1
		else:
			return 0


	def Y(self,other):
		s = self.GraspPose.pose.position.y
		o = other.GraspPose.pose.position.y

		if s > o:
			return 1
		elif  s < o:
			return -1
		else:
			return 0


	def _Y(self,other):
		s = self.GraspPose.pose.position.y
		o = other.GraspPose.pose.position.y

		if s > o:
			return -1
		elif  s < o:
			return 1
		else:
			return 0
	###### [/GRASP FILTERS ] ##################################################

	def minZ(self,other):
		s = self.G2.pose.position.z
		o = other.G2.pose.position.z

		if s > o:
			return 1
		elif  s < o:
			return -1
		else:
			return 0
	


#################################################################################################
###################################### CONVERTERS ###############################################
#################################################################################################
# Convert OpenRAVE to Gazebo format.
def OR_to_ROS(OR):
	return [OR[2], OR[3], OR[4], OR[0], OR[1], OR[5], OR[6]]


# Convert Gazebo to OpenRAVE format.
def ROS_to_OR(ROS):
	return [ROS[3], ROS[4], ROS[0], ROS[1], ROS[2], ROS[5], ROS[6]]


# Convert /sdh_controller/command to script_server/sdh/joint_names
def sdh_controller_TO_script_server(values):
	#/sdh_controller/command
	#sdh_knuckle_joint", "sdh_finger_12_joint", "sdh_finger_13_joint", "sdh_finger_22_joint", "sdh_finger_23_joint", "sdh_thumb_2_joint", "sdh_thumb_3_joint

	#/script_server/sdh/joint_names
	#sdh_knuckle_joint, sdh_thumb_2_joint, sdh_thumb_3_joint, sdh_finger_12_joint, sdh_finger_13_joint,sdh_finger_22_joint, sdh_finger_23_joint
	values = eval(values)
	return [[values[0], values[5], values[6], values[1], values[2], values[3], values[4]]]


# Convert GraspConfig to msg format.
def graspConfig_to_MSG(res):
	aux = []
	res = res[0]
	for i in range(0,len(res)):
		aux.append(grasp(str(res[i].joint_values), res[i].GraspPose, float(res[i].MinDist), float(res[i].MinDist)))
	return [aux]


# Convert GraspConfig to matrix.
def matrix_from_graspPose(gp):

	q = []
	q.append(gp.pose.orientation.x)
	q.append(gp.pose.orientation.y)
	q.append(gp.pose.orientation.z)
	q.append(gp.pose.orientation.w)
	e = euler_from_quaternion(q, axes='sxyz')

	matrix = euler_matrix(e[0],e[1],e[2] ,axes='sxyz')
	matrix[0][3] = gp.pose.position.x
	matrix[1][3] = gp.pose.position.y
	matrix[2][3] = gp.pose.position.z

	return matrix


# Convert string list to float list (needed for OR).
def stringList_to_ORformat(OR):
	res = [0 for i in range(28)]	

	OR = ROS_to_OR(eval(OR))

	for i in range (0,len(OR)):
		res[i+7] = float(OR[i])

	return res


#################################################################################################
############################## GRASPING FUNCTIONS ###############################################
#################################################################################################
# -----------------------------------------------------------------------------------------------
# XML file generator.
# -----------------------------------------------------------------------------------------------
def generateFile(targetName, gmodel, env):

	# ------------------------ 
	# <targetName_all_grasps>.xml
	# ------------------------ 

	f_name = targetName + "_all_grasps.xml"

	try:
		f = open(package_path+'/DB/'+f_name,'r')
		print "There are a file with the same name."
		sys.exit()
	except:
		f = open(package_path+'/DB/'+f_name,'w')
		f.write("<?xml version=\"1.0\" ?>\n")
		f.write("<GraspList>\n")
		f.write("<ObjectID>"+targetName+"</ObjectID>\n")
		f.write("<HAND>SDH</HAND>\n")
		f.write("<joint_names>[sdh_knuckle_joint, sdh_finger_12_joint, sdh_finger_13_joint, sdh_finger_22_joint, sdh_finger_23_joint, sdh_thumb_2_joint, sdh_thumb_3_joint]</joint_names>\n")
		f.write("<reference_link>sdh_palm_link</reference_link>\n")
		f.write("<configuration id=\"0\">\n")


		cont = 0
		print "Adding grasps to the new XML file..."
		for i in range(0, len(gmodel.grasps)):
			print str(i+1)+"/"+str(len(gmodel.grasps))
			try:
	 			contacts,finalconfig,mindist,volume = gmodel.testGrasp(grasp=gmodel.grasps[i],translate=True,forceclosure=True)
				#care-o-bot3.zae
				value = (finalconfig[0])[7:14]	
				value = OR_to_ROS(value)
				j = value


				if not (j[1]>=-1.15 and j[3]>=-1.15 and j[5]>=-1.25 and j[1]<=1 and j[3]<=1 and j[5]<=1 and j[2]>-0.5 and j[4]>-0.5 and j[6]>-0.5):
					continue

			   	f.write("<Grasp Index=\""+str(cont)+"\">\n")
			   	
                value = sdh_controller_TO_script_server(value)
				f.write("<joint_values>"+str(value)+"</joint_values>\n")

				# [Valores relativos al palm_link]
			   	f.write("<GraspPose>\n")
				robot = env.GetRobots()[0]
				robot.GetController().Reset(0)
				robot.SetDOFValues(finalconfig[0])
				robot.SetTransform(finalconfig[1])
				env.UpdatePublishedBodies()

				index = (robot.GetLink("sdh_palm_link")).GetIndex()
				matrix = (robot.GetLinkTransformations())[index]
				t = translation_from_matrix(matrix)
				e = euler_from_matrix(matrix, axes='sxyz')
				f.write("<Translation>["+str(t[0])+", "+str(t[1])+", "+str(t[2])+"]</Translation>\n")
				f.write("<Rotation>["+str(e[0])+", "+str(e[1])+", "+str(e[2])+"]</Rotation>\n")
			   	f.write("</GraspPose>\n")


			   	f.write("<MinDist>"+str(mindist)+"</MinDist>\n")
			   	f.write("<Volume>"+str(volume)+"</Volume>\n")

			   	f.write("</Grasp>\n")

				cont += 1
			
			except:
				continue


		f.write("<NumberOfGrasps>"+str(cont)+"</NumberOfGrasps>\n")
		f.write("</configuration>\n")
		f.write("</GraspList>")
		f.close()
		print "%d grasps have been added to the XML file..." %cont


# -----------------------------------------------------------------------------------------------
# Get grasps
# -----------------------------------------------------------------------------------------------
def getGrasps(file_name, pose=None, num=0, msg=False):

	xmldoc = minidom.parse(file_name)  
	padres = ((xmldoc.firstChild)).getElementsByTagName('configuration')

	res = []
	for j in range(0, len(padres)):
		hijos = (((xmldoc.firstChild)).getElementsByTagName('configuration'))[j].getElementsByTagName('Grasp')
		grasps = []
		for i in range(0,len(hijos)):
			joint_values = ((hijos[i].getElementsByTagName('joint_values'))[0]).firstChild.nodeValue

			aux = ((hijos[i].getElementsByTagName('GraspPose'))[0])
			Translation = eval((aux.getElementsByTagName('Translation')[0]).firstChild.nodeValue)
			Rotation = eval((aux.getElementsByTagName('Rotation')[0]).firstChild.nodeValue)
			g = PoseStamped()
			g.pose.position.x = float(Translation[0])
			g.pose.position.y = float(Translation[1])
			g.pose.position.z = float(Translation[2])
			Rotation =  quaternion_from_euler(Rotation[0], Rotation[1], Rotation[2], axes='sxyz')
			g.pose.orientation.x = float(Rotation[0])
			g.pose.orientation.y = float(Rotation[1])
			g.pose.orientation.z = float(Rotation[2])
			g.pose.orientation.w = float(Rotation[3])

			aux = ((hijos[i].getElementsByTagName('G2'))[0])
			Translation = eval((aux.getElementsByTagName('TG')[0]).firstChild.nodeValue)
			Rotation = eval((aux.getElementsByTagName('TR')[0]).firstChild.nodeValue)
			g2 = PoseStamped()
			g2.pose.position.x = float(Translation[0])
			g2.pose.position.y = float(Translation[1])
			g2.pose.position.z = float(Translation[2])
			Rotation =  quaternion_from_euler(Rotation[0], Rotation[1], Rotation[2], axes='sxyz')
			g2.pose.orientation.x = float(Rotation[0])
			g2.pose.orientation.y = float(Rotation[1])
			g2.pose.orientation.z = float(Rotation[2])
			g2.pose.orientation.w = float(Rotation[3])




			MinDist = ((hijos[i].getElementsByTagName('MinDist'))[0]).firstChild.nodeValue
			Volume = ((hijos[i].getElementsByTagName('Volume'))[0]).firstChild.nodeValue

			grasps.append(GraspConfig(joint_values, g, MinDist, Volume))

		#grasps = grasp_filter(grasps)

		if pose=="Z":
			grasps.sort(GraspConfig.Z)
			grasps = Zfilter(grasps)
		elif pose=="_Z":	
			grasps.sort(GraspConfig._Z)
			grasps = _Zfilter(grasps)
		elif pose=="X":	
			grasps.sort(GraspConfig.X)
			grasps = Xfilter(grasps)
		elif pose=="_X":	
			grasps.sort(GraspConfig._X)
			grasps = Xfilter(grasps)
		elif pose=="Y":	
			grasps.sort(GraspConfig.Y)
			grasps = Yfilter(grasps)
		else:	
			grasps.sort(GraspConfig._Y)
			grasps = Yfilter(grasps)

		if num==0:
			num=len(grasps)
		
		res.append(grasps[0:num])


	if msg==False:
		return res					#returns a GraspConfig list (openrave viewer)
	else:
		return 	graspConfig_to_MSG(res)			#returns a msg list (server/service)


# -----------------------------------------------------------------------------------------------
# Grasp function
# -----------------------------------------------------------------------------------------------
def Grasp(values):
	"""
	pub = rospy.Publisher('/sdh_controller/command', JointTrajectory, latch=True)

	jt = JointTrajectory()
	jt.joint_names = ["sdh_knuckle_joint", "sdh_finger_12_joint", "sdh_finger_13_joint", "sdh_finger_22_joint", "sdh_finger_23_joint", "sdh_thumb_2_joint", "sdh_thumb_3_joint"]
	jt.points = []
	jt.points.append(JointTrajectoryPoint())
	jt.points[0].positions = eval(values)
	jt.points[0].time_from_start.secs = 3

	pub.publish(jt)
	"""

	sss.move("sdh", sdh_controller_TO_script_server(values))

	
	
# -----------------------------------------------------------------------------------------------
# Remove grasps in wich the fingers are in a extrange position. (obsolet, we have filtered all the filter)
# -----------------------------------------------------------------------------------------------
def grasp_filter(g):
	grasps = []
	for i in range(0,len(g)):
		j = eval(g[i].joint_values)
		#if abs(j[1])<=pi/2.75 and abs(j[3])<=pi/2.75 and abs(j[5])<=pi/2.45:
		if (j[1]>=-1.15 and j[3]>=-1.15 and j[5]>=-1.25 and j[1]<=1 and j[3]<=1 and j[5]<=1) and j[2]>-0.5 and j[4]>-0.5 and j[6]>-0.5:
			grasps.append(g[i])

	return grasps


# -----------------------------------------------------------------------------------------------
# Shows the grasps in OpenRAVE
# -----------------------------------------------------------------------------------------------
def showOR(env, grasps, delay=0.5, depurador=False):
	g = []

	env.SetViewer('qtcoin')
	time.sleep(1.0)

	if depurador==True:
		print "Write <save> to save the current configuration and <end> to finish."

	manip = ((env.GetRobots()[0]).GetManipulator("arm"))
	robot = env.GetRobots()[0]
	with openravepy.databases.grasping.GraspingModel.GripperVisibility(manip):

		for i in range(0,len(grasps)):
			print 'grasp %d/%d'%(i,len(grasps))

			robot.SetDOFValues(stringList_to_ORformat(grasps[i].joint_values))
			Tgrasp = matrix_from_graspPose(grasps[i].GraspPose)

			index = (robot.GetLink("sdh_palm_link")).GetIndex()
			matrix = (robot.GetLinkTransformations())[index]
			Tdelta = dot(Tgrasp,linalg.inv(matrix))
			for link in manip.GetChildLinks():
				link.SetTransform(dot(Tdelta,link.GetTransform()))

			env.UpdatePublishedBodies()


			if depurador==True:
				res = raw_input("?: " )
				if res=="save":
					g.append(grasps[i])
				if res=="end": 
					return g
			else:
				if delay is None:
					raw_input('Next config.')
				elif delay > 0:
					time.sleep(delay)
	return g
	




###### [ GRASP FILTERS ] ##################################################
def _Zfilter(grasps):
	aux = []
	for i in range(0,len(grasps)):
		g = abs(grasps[i].GraspPose.pose.orientation.w)
		if g > 0 and g < 0.1:
			aux.append(grasps[i])
		else:
			break
	return aux


def Zfilter(grasps):
	aux = []
	for i in range(0,len(grasps)):
		g1 = abs(grasps[i].GraspPose.pose.orientation.x)
		g2 = abs(grasps[i].GraspPose.pose.orientation.y)
		if g1<0.09 and g2<0.09:
			aux.append(grasps[i])
		else:
			break
	return aux


def Xfilter(grasps):
	aux = []
	for i in range(0,len(grasps)):
		g1 = abs(grasps[i].GraspPose.pose.orientation.x)
		if g1>0.4 and g1<0.8:
			aux.append(grasps[i])
		else:
			break

	aux = aux[0:len(aux)-5]
	aux.sort(GraspConfig._Z)

	p = int(len(aux)*0.15)
	aux = aux[p:len(aux)-p]
	return aux


def Yfilter(grasps):
	aux = []
	for i in range(0,len(grasps)):
		x = abs(grasps[i].GraspPose.pose.orientation.x)
		y= abs(grasps[i].GraspPose.pose.orientation.y)
		if (x<0.1 and (y>0.6 and y<0.8)) or (y<0.1 and (x>0.6 and x<0.8)):
			aux.append(grasps[i])
		else:
			break

	aux = aux[0:len(aux)-5]
	aux.sort(GraspConfig._Z)

	p = int(len(aux)*0.15)
	aux = aux[p:len(aux)-p]
	return aux



	





