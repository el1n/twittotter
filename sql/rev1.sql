-- phpMyAdmin SQL Dump
-- version 2.11.11.3
-- http://www.phpmyadmin.net
--
-- Host: 127.0.0.1
-- Generation Time: Jan 23, 2012 at 12:46 PM
-- Server version: 5.0.77
-- PHP Version: 5.1.6

SET SQL_MODE="NO_AUTO_VALUE_ON_ZERO";

--
-- Database: `twihome_test`
--

-- --------------------------------------------------------

--
-- Table structure for table `Queue`
--

CREATE TABLE IF NOT EXISTS `Queue` (
  `id` bigint(20) unsigned NOT NULL auto_increment,
  `screen_name` varchar(16) default NULL,
  `order` varchar(255) default NULL,
  `flag` bigint(20) unsigned NOT NULL default '1',
  `priority` tinyint(4) NOT NULL default '1',
  `ctime` timestamp NOT NULL default CURRENT_TIMESTAMP,
  `revision` int(11) NOT NULL default '1',
  PRIMARY KEY  (`id`),
  KEY `screen_name` (`screen_name`,`ctime`)
) ENGINE=InnoDB  DEFAULT CHARSET=utf8 AUTO_INCREMENT=7 ;

-- --------------------------------------------------------

--
-- Table structure for table `Token`
--

CREATE TABLE IF NOT EXISTS `Token` (
  `id` bigint(20) unsigned NOT NULL,
  `screen_name` varchar(16) default NULL,
  `ACCESS_TOKEN` varchar(255) default NULL,
  `ACCESS_TOKEN_SECRET` varchar(255) default NULL,
  `ctime` timestamp NOT NULL default CURRENT_TIMESTAMP,
  `revision` int(11) NOT NULL default '1',
  PRIMARY KEY  (`id`),
  UNIQUE KEY `screen_name` (`screen_name`,`ACCESS_TOKEN`,`ACCESS_TOKEN_SECRET`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Table structure for table `Tweet`
--

CREATE TABLE IF NOT EXISTS `Tweet` (
  `id` bigint(20) unsigned NOT NULL,
  `screen_name` varchar(16) default NULL,
  `text` varchar(255) NOT NULL,
  `created_at` datetime default NULL,
  `structure` mediumblob,
  `flag` bigint(20) unsigned NOT NULL default '0',
  `revision` int(11) NOT NULL default '1',
  PRIMARY KEY  (`id`),
  KEY `screen_name` (`screen_name`,`text`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
